"""Regression tests for reproduced coordinator bugs, run on the fake backend and fake clock."""

from __future__ import annotations

import asyncio
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest
from test_execution_coordinator import (
    STAMP,
    _complete_plan_before_decision,
    _coordinator,
    _create_run,
    _decision_result,
    _worker_script,
)

from orchestrator.backends.fake import AttemptScript, FakeBackend, FakeClock, ScriptedFailure
from orchestrator.backends.fake_decision import DecisionBarrier, FakeDecisionEngine
from orchestrator.domain.backend import (
    Reconciliation,
    WorkerDisconnectedEvent,
    WorkerEventKind,
    WorkerFailureEvent,
)
from orchestrator.domain.models import (
    AttemptStatus,
    FailureClass,
    InterventionKind,
    PauseIntervention,
    ResumeIntervention,
    RetryIntervention,
    RunStatus,
    StopAttemptIntervention,
    StopIntervention,
)
from orchestrator.execution import ExecutionCoordinator
from orchestrator.persistence import CoordinatorOwnership, SQLiteLedger


@pytest.fixture
def ledger_owner(tmp_path):
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    ownership = CoordinatorOwnership(ledger, tmp_path / "coordinator.lock")
    ownership.acquire("test-owner", STAMP)
    yield ledger, ownership
    ownership.release(STAMP)
    ledger.close()


async def _settle_loop(turns: int = 20) -> None:
    for _ in range(turns):
        await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_clock_tick_before_deadline_keeps_the_worker_event_stream(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r1")
    coordinator, backend, clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(events=_worker_script(spec).events, event_barrier=True),
        auto_release=False,
    )
    coordinator.advance("r1")
    coordinator.advance("r1")
    await coordinator.dispatch_pending("r1")
    attempt_id = ledger.list_attempts("r1")[0].spec.attempt_id
    await backend.wait_until_waiting(attempt_id, 0)

    clock.advance(1)  # far below the profile timeout
    await _settle_loop()
    backend.release_next(attempt_id)
    await coordinator.wait_for_workers()

    assert ledger.get_attempt(attempt_id).state.status is AttemptStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_failed_run_stays_failed_when_a_sibling_attempt_settles(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "research", "r2")
    first: dict[str, str] = {}

    def factory(spec):
        if not first:
            first["id"] = spec.attempt_id
            return AttemptScript(
                events=(),
                start_failure=ScriptedFailure(
                    FailureClass.CONFIGURATION, "bad config", safe_to_retry=False
                ),
            )
        return AttemptScript(events=_worker_script(spec).events, event_barrier=True)

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance("r2")
    coordinator.advance("r2")
    await coordinator.dispatch_pending("r2")
    coordinator.advance("r2")
    assert ledger.get_run("r2").state.status is RunStatus.FAILED
    survivor = next(a for a in ledger.list_attempts("r2") if a.spec.attempt_id != first["id"])
    await backend.wait_until_waiting(survivor.spec.attempt_id, 0)

    backend.release_next(survivor.spec.attempt_id)
    await coordinator.wait_for_workers()

    assert ledger.get_run("r2").state.status is RunStatus.FAILED
    assert ledger.get_attempt(survivor.spec.attempt_id).state.status is AttemptStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_failure_settlement_keeps_the_reconciliation_attention_reason(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    run_id = "r6"
    first_attempt = str(uuid5(NAMESPACE_URL, f"{run_id}/research/research/slot-01/1"))
    _create_run(ledger, app_config, "research", run_id)

    failed_once: list[str] = []

    def factory(spec):
        if spec.attempt_id == first_attempt:
            good = _worker_script(spec).events[0]
            return AttemptScript(
                events=(
                    WorkerDisconnectedEvent(
                        kind=WorkerEventKind.DISCONNECTED,
                        attempt_id=first_attempt,
                        sequence=1,
                        reason="socket closed",
                    ),
                ),
                reconciliations=(
                    Reconciliation(
                        known=True,
                        status=AttemptStatus.SUCCEEDED,
                        terminal_result=good.result,
                    ),
                ),
                event_barrier=False,
            )
        if not failed_once:
            failed_once.append(spec.attempt_id)
            return AttemptScript(
                events=(
                    WorkerFailureEvent(
                        kind=WorkerEventKind.FAILED,
                        attempt_id=spec.attempt_id,
                        sequence=1,
                        failure_class=FailureClass.PROVIDER_TRANSIENT,
                        summary="slot-02 transient failure",
                        safe_to_retry=True,
                    ),
                ),
                event_barrier=True,
            )
        return AttemptScript(events=_worker_script(spec).events, event_barrier=False)

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance(run_id)
    coordinator.advance(run_id)
    await asyncio.wait_for(coordinator.dispatch_pending(run_id), 5)
    other = next(a for a in ledger.list_attempts(run_id) if a.spec.attempt_id != first_attempt)
    await asyncio.wait_for(backend.wait_until_waiting(other.spec.attempt_id, 0), 5)
    await _settle_loop()
    reason_before = ledger.get_run(run_id).state.attention_reason
    assert reason_before is not None and reason_before.startswith("reconciliation pending")

    backend.release_next(other.spec.attempt_id)
    await asyncio.wait_for(coordinator.wait_for_workers(), 5)
    assert ledger.get_run(run_id).state.attention_reason == reason_before

    await asyncio.wait_for(coordinator.recover(run_id), 5)
    status = await asyncio.wait_for(coordinator.run_until_stalled(run_id), 5)

    assert status is RunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_pause_between_admission_and_launch_does_not_spend_the_retry_budget(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r3")
    coordinator, backend, _clock = _coordinator(ledger, ownership, factory=_worker_script)
    coordinator.advance("r3")
    coordinator.advance("r3")  # attempt admitted: launching, launch intent still pending
    assert ledger.list_attempts("r3")[0].state.status is AttemptStatus.LAUNCHING

    await coordinator.apply_intervention(_control(PauseIntervention, ledger, "r3"))
    await coordinator.apply_intervention(_control(ResumeIntervention, ledger, "r3"))
    status = await coordinator.run_until_stalled("r3")

    assert status is RunStatus.SUCCEEDED
    assert len(backend.start_calls) == 1


def _control(kind, ledger, run_id, **extra):
    return kind(
        command_id=uuid4(),
        actor="user",
        target=extra.get("attempt_id", run_id),
        expected_run_revision=ledger.get_run(run_id).state.revision,
        kind=_KINDS[kind],
        run_id=run_id,
        **extra,
    )


_KINDS = {
    PauseIntervention: InterventionKind.PAUSE,
    ResumeIntervention: InterventionKind.RESUME,
    StopIntervention: InterventionKind.STOP,
    RetryIntervention: InterventionKind.RETRY,
}


class _PreflightRaises(FakeBackend):
    async def preflight(self, spec, context=None):
        raise ConnectionError("backend unreachable during preflight")


@pytest.mark.asyncio
async def test_exception_from_preflight_is_a_known_failure_that_releases_reservations(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r7")
    clock = FakeClock(origin=STAMP)
    backend = _PreflightRaises(backend_id="codex", script_factory=_worker_script, clock=clock)
    coordinator = ExecutionCoordinator(ledger, backend, ownership, clock=clock)
    coordinator.advance("r7")
    coordinator.advance("r7")

    await coordinator.dispatch_pending("r7")

    attempt = ledger.list_attempts("r7")[0]
    assert backend.start_calls == []
    assert attempt.state.status is AttemptStatus.FAILED
    assert not any(item.status.value == "held" for item in ledger.list_reservations("r7"))


@pytest.mark.asyncio
async def test_stop_during_start_survives_the_late_launch_acknowledgement(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r4")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(events=_worker_script(spec).events, start_barrier=True),
    )
    coordinator.advance("r4")
    coordinator.advance("r4")
    dispatch = asyncio.create_task(coordinator.dispatch_pending("r4"))
    attempt_id = ledger.list_attempts("r4")[0].spec.attempt_id
    await asyncio.wait_for(backend.wait_until_start_waiting(attempt_id), 5)

    await coordinator.apply_intervention(_control(StopIntervention, ledger, "r4"))
    run = ledger.get_run("r4")
    assert run.state.status is RunStatus.ATTENTION_REQUIRED
    assert run.state.resume_status is RunStatus.STOPPING
    assert ledger.get_attempt(attempt_id).state.status is AttemptStatus.OUTCOME_UNKNOWN

    backend.release_start(attempt_id)
    await asyncio.wait_for(dispatch, 5)

    # The late acknowledgement must not turn the ambiguous attempt back into a running one.
    assert ledger.get_attempt(attempt_id).state.status is not AttemptStatus.RUNNING


@pytest.mark.asyncio
async def test_retry_on_a_paused_run_does_not_lift_the_pause(app_config, ledger_owner) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r5")
    failed_once: list[str] = []

    def factory(spec):
        if not failed_once:
            failed_once.append(spec.attempt_id)
            return AttemptScript(
                events=(
                    WorkerFailureEvent(
                        kind=WorkerEventKind.FAILED,
                        attempt_id=spec.attempt_id,
                        sequence=1,
                        failure_class=FailureClass.PROVIDER_TRANSIENT,
                        summary="transient",
                        safe_to_retry=True,
                    ),
                ),
                event_barrier=True,
            )
        return _worker_script(spec)

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance("r5")
    coordinator.advance("r5")
    await coordinator.dispatch_pending("r5")
    attempt_id = ledger.list_attempts("r5")[0].spec.attempt_id
    await asyncio.wait_for(backend.wait_until_waiting(attempt_id, 0), 5)
    await coordinator.apply_intervention(_control(PauseIntervention, ledger, "r5"))
    backend.release_next(attempt_id)
    await asyncio.wait_for(coordinator.wait_for_workers(), 5)
    assert ledger.get_run("r5").state.status is RunStatus.PAUSED

    await coordinator.apply_intervention(
        _control(RetryIntervention, ledger, "r5", attempt_id=attempt_id)
    )

    assert ledger.get_run("r5").state.status is RunStatus.PAUSED
    assert len(backend.start_calls) == 1


@pytest.mark.asyncio
async def test_decision_gone_stale_while_pausing_is_asked_again_after_resume(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "p")
    _complete_plan_before_decision(ledger, "p")
    barrier = DecisionBarrier()
    engine = FakeDecisionEngine(
        (
            lambda request: _decision_result(request, outcome_id="implementer"),
            lambda request: _decision_result(request, outcome_id="implementer"),
        ),
        barrier=barrier,
    )
    coordinator, _, _ = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=engine
    )
    task = asyncio.create_task(asyncio.wait_for(coordinator.run_until_stalled("p"), 5))
    await asyncio.wait_for(barrier.entered.wait(), 5)
    await coordinator.apply_intervention(
        PauseIntervention(
            command_id=uuid4(),
            actor="user",
            target="p",
            expected_run_revision=ledger.get_run("p").state.revision,
            kind=InterventionKind.PAUSE,
            run_id="p",
        )
    )
    barrier.release.set()
    await task
    assert ledger.get_run("p").state.status == RunStatus.PAUSED
    assert ledger.get_stage_redirect("p", "implement") is None

    await coordinator.apply_intervention(
        ResumeIntervention(
            command_id=uuid4(),
            actor="user",
            target="p",
            expected_run_revision=ledger.get_run("p").state.revision,
            kind=InterventionKind.RESUME,
            run_id="p",
        )
    )
    await asyncio.wait_for(coordinator.run_until_stalled("p"), 5)

    assert len(engine.requests) == 2
    assert ledger.get_stage_redirect("p", "implement") == "implementer"


@pytest.mark.asyncio
async def test_cancelling_an_unlaunched_attempt_keeps_the_attention_hold(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r8")
    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=_worker_script)
    coordinator.advance("r8")
    coordinator.advance("r8")  # attempt admitted: launching, launch intent still pending
    coordinator._set_run_status(ledger.get_run("r8"), RunStatus.ATTENTION_REQUIRED, "operator hold")

    await coordinator.dispatch_pending("r8")

    run = ledger.get_run("r8")
    assert ledger.list_attempts("r8")[0].state.status is AttemptStatus.CANCELLED
    assert run.state.status is RunStatus.ATTENTION_REQUIRED
    assert run.state.attention_reason == "operator hold"
    assert run.state.resume_status is not None


class _FailsTheRunDuringInterrupt(FakeBackend):
    """Ends the run the way a failing sibling stage would, while a stop delivery is in flight."""

    coordinator: ExecutionCoordinator
    run_id: str

    async def interrupt(self, handle, command_id):
        self.coordinator._set_run_status(
            self.coordinator.ledger.get_run(self.run_id), RunStatus.FAILED, "sibling stage failed"
        )
        return await super().interrupt(handle, command_id)


@pytest.mark.asyncio
async def test_late_stop_delivery_keeps_a_failed_run_failed(app_config, ledger_owner) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r9")
    clock = FakeClock(origin=STAMP)
    backend = _FailsTheRunDuringInterrupt(
        backend_id="codex",
        script_factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events, event_barrier=True
        ),
        clock=clock,
        auto_release=False,
    )
    coordinator = ExecutionCoordinator(ledger, backend, ownership, clock=clock)
    backend.coordinator = coordinator
    backend.run_id = "r9"
    coordinator.advance("r9")
    coordinator.advance("r9")
    await coordinator.dispatch_pending("r9")
    attempt_id = ledger.list_attempts("r9")[0].spec.attempt_id
    await asyncio.wait_for(backend.wait_until_waiting(attempt_id, 0), 5)

    await coordinator.apply_intervention(
        StopAttemptIntervention(
            command_id=uuid4(),
            actor="user",
            target=attempt_id,
            expected_run_revision=ledger.get_run("r9").state.revision,
            kind=InterventionKind.STOP_ATTEMPT,
            run_id="r9",
            attempt_id=attempt_id,
        )
    )

    assert ledger.get_run("r9").state.status is RunStatus.FAILED


@pytest.mark.asyncio
async def test_manual_retry_budget_ignores_never_launched_attempts(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "r10")
    launched: list[str] = []

    def factory(spec):
        launched.append(spec.attempt_id)
        if len(launched) == 1:
            return AttemptScript(
                events=(
                    WorkerFailureEvent(
                        kind=WorkerEventKind.FAILED,
                        attempt_id=spec.attempt_id,
                        sequence=1,
                        failure_class=FailureClass.PROVIDER_TRANSIENT,
                        summary="transient",
                        safe_to_retry=True,
                    ),
                ),
                event_barrier=True,
            )
        return _worker_script(spec)

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance("r10")
    coordinator.advance("r10")  # admitted, never launched
    await coordinator.apply_intervention(_control(PauseIntervention, ledger, "r10"))
    await coordinator.dispatch_pending("r10")  # cancels it before any worker starts
    await coordinator.apply_intervention(_control(ResumeIntervention, ledger, "r10"))
    coordinator.advance("r10")
    coordinator.advance("r10")
    await coordinator.dispatch_pending("r10")
    launched_attempt = next(
        item for item in ledger.list_attempts("r10") if item.spec.attempt_id in launched
    )
    await asyncio.wait_for(backend.wait_until_waiting(launched_attempt.spec.attempt_id, 0), 5)
    await coordinator.apply_intervention(_control(PauseIntervention, ledger, "r10"))
    backend.release_next(launched_attempt.spec.attempt_id)
    await asyncio.wait_for(coordinator.wait_for_workers(), 5)
    assert len(ledger.list_attempts("r10", launched_attempt.stage_id)) >= 2

    result = await coordinator.apply_intervention(
        _control(RetryIntervention, ledger, "r10", attempt_id=launched_attempt.spec.attempt_id)
    )

    assert result.outcome.value == "accepted"
