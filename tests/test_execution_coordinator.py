from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from orchestrator.backends.fake import (
    AttemptScript,
    FakeBackend,
    FakeClock,
    ScriptedFailure,
)
from orchestrator.domain.backend import (
    ArtifactEntry,
    OutputStatus,
    WorkerResult,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import (
    Effort,
    FailureClass,
    ModelBindingSettings,
    ResolvedWorkflow,
    RunOverrides,
    RunStatus,
    StageStatus,
)
from orchestrator.execution import (
    ExecutionCoordinator,
    InputResolutionError,
    resolve_stage_inputs,
    resolve_stage_slots,
)
from orchestrator.persistence import CoordinatorOwnership, SQLiteLedger
from orchestrator.persistence.ledger import canonical_json, content_hash
from orchestrator.resolution import resolve_run

STAMP = datetime(2026, 9, 29, tzinfo=UTC)
OUTPUTS = {
    "plan": "plan",
    "implement": "changes",
    "repair": "changes",
    "diagnose": "diagnosis",
    "review": "report",
    "test": "report",
    "rereview": "report",
    "retest": "report",
    "validate": "report",
    "research": "findings",
    "synthesize": "synthesis",
    "verify": "report",
    "handoff": "summary",
    "summary": "summary",
}


@pytest.fixture
def ledger_owner(tmp_path):
    ledger = SQLiteLedger(tmp_path / "ledger.sqlite3")
    ownership = CoordinatorOwnership(ledger, tmp_path / "coordinator.lock")
    ownership.acquire("test-owner", STAMP)
    yield ledger, ownership
    ownership.release(STAMP)
    ledger.close()


def _resolved_run(app_config, workflow_id: str, *, project=None, workflow=None, overrides=None):
    source_project = project or app_config.project
    source_project = source_project.model_copy(
        update={
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex",
                    model_id="offline-model",
                    allowed_efforts=[Effort.HIGH, Effort.MEDIUM],
                )
            }
        }
    )
    source_workflow = workflow or next(
        item for item in app_config.workflows if item.id == workflow_id
    )
    spec = resolve_run(
        "Implement and verify a small feature",
        source_project,
        source_workflow,
        app_config.agents.agents,
        model_availability={"codex": {"offline-model": {Effort.HIGH, Effort.MEDIUM}}},
        overrides=overrides,
    )
    return source_project, spec


def _create_run(
    ledger,
    app_config,
    workflow_id: str,
    run_id: str,
    *,
    project=None,
    workflow=None,
    overrides=None,
):
    source_project, spec = _resolved_run(
        app_config,
        workflow_id,
        project=project,
        workflow=workflow,
        overrides=overrides,
    )
    ledger.create_run(run_id, source_project, spec, uuid4(), actor="test", occurred_at=STAMP)
    return spec


def _worker_script(spec, *, statuses=None):
    stage_id = spec.stage_id
    assert stage_id is not None
    output_name = OUTPUTS[stage_id]
    status = (statuses or {}).get(stage_id, OutputStatus.PASS)
    result = WorkerResult(
        attempt_id=spec.attempt_id,
        input_revision=content_hash(canonical_json(spec.input_manifest)),
        workspace_revision=spec.workspace_revision,
        status=status,
        summary="limitations: scripted fake evidence; unresolved claims are labelled",
        artifacts=(
            ArtifactEntry(
                name=output_name,
                schema_id=f"{output_name}-v1",
                content_hash=hashlib.sha256(
                    f"{spec.attempt_id}:{output_name}".encode()
                ).hexdigest(),
            ),
        ),
    )
    event = WorkerTerminalEvent(
        kind="terminal",
        attempt_id=spec.attempt_id,
        sequence=1,
        result=result,
    )
    return AttemptScript(events=(event,))


def _coordinator(ledger, ownership, *, factory, auto_release=True, cap=4):
    clock = FakeClock(origin=STAMP)
    backend = FakeBackend(
        backend_id="codex",
        script_factory=factory,
        auto_release=auto_release,
        clock=clock,
    )
    return (
        ExecutionCoordinator(
            ledger,
            backend,
            ownership,
            clock=clock,
            global_parallelism=cap,
        ),
        backend,
        clock,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "workflow_id", ["review", "prototype", "feature", "debug", "research", "handoff"]
)
async def test_all_shipped_workflows_complete_offline(
    workflow_id, tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    spec = _create_run(ledger, app_config, workflow_id, f"run-{workflow_id}")
    coordinator, backend, _clock = _coordinator(ledger, ownership, factory=_worker_script)

    status = await coordinator.run_until_stalled(f"run-{workflow_id}")

    run = ledger.get_run(f"run-{workflow_id}")
    assert status == RunStatus.SUCCEEDED
    assert run.state.status == RunStatus.SUCCEEDED
    assert all(stage.status in {StageStatus.SUCCEEDED, StageStatus.SKIPPED} for stage in run.stages)
    assert all(
        action.status.value == "acknowledged" for action in ledger.list_outbox_actions(run.run_id)
    )
    stage_status = {stage.stage_id: stage.status for stage in run.stages}
    assert len(backend.start_calls) == sum(
        selection.worker_count
        for selection in spec.selections
        if stage_status[selection.stage_id] == StageStatus.SUCCEEDED
    )


@pytest.mark.asyncio
async def test_feature_repair_branch_requires_current_revision_verification(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "feature", "feature-repair")
    coordinator, _backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: _worker_script(
            spec,
            statuses={
                "review": OutputStatus.FAIL,
                "test": OutputStatus.FAIL,
            },
        ),
    )

    status = await coordinator.run_until_stalled("feature-repair")

    run = ledger.get_run("feature-repair")
    stages = {stage.stage_id: stage for stage in run.stages}
    assert status == RunStatus.SUCCEEDED
    assert stages["repair_gate"].result.decision == "repair_needed"
    assert stages["rereview"].result.result_status == OutputStatus.PASS
    assert stages["retest"].result.result_status == OutputStatus.PASS
    assert stages["review"].result.result_status == OutputStatus.FAIL
    assert stages["test"].result.result_status == OutputStatus.FAIL
    assert (
        stages["integrate_repair"].result.workspace_revision
        != stages["integrate"].result.workspace_revision
    )


@pytest.mark.asyncio
async def test_failed_second_feature_verification_does_not_accept_old_evidence(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "feature", "feature-failed-repair")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: _worker_script(
            spec,
            statuses={
                "review": OutputStatus.FAIL,
                "test": OutputStatus.FAIL,
                "rereview": OutputStatus.FAIL,
            },
        ),
    )

    status = await coordinator.run_until_stalled("feature-failed-repair")
    run = ledger.get_run("feature-failed-repair")
    stages = {stage.stage_id: stage for stage in run.stages}

    assert status == RunStatus.FAILED
    assert stages["review"].result.result_status == OutputStatus.FAIL
    assert stages["rereview"].status == StageStatus.FAILED
    assert stages["handoff"].status == StageStatus.PENDING
    assert all(
        attempt.spec.stage_id != "handoff"
        for attempt in ledger.list_attempts("feature-failed-repair")
    )
    assert len(backend.start_calls) == len(ledger.list_outbox_actions("feature-failed-repair"))


@pytest.mark.asyncio
async def test_known_retry_creates_new_attempt_and_preserves_parent_lineage(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "retry-run")

    def factory(spec):
        if spec.parent_attempt_id is None:
            return AttemptScript(
                events=(),
                start_failure=ScriptedFailure(
                    failure_class=FailureClass.PROVIDER_TRANSIENT,
                    summary="scripted prelaunch outage",
                    safe_to_retry=True,
                ),
            )
        return _worker_script(spec)

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=factory)
    status = await coordinator.run_until_stalled("retry-run")
    attempts = ledger.list_attempts("retry-run", "review")
    first = next(item for item in attempts if item.spec.parent_attempt_id is None)
    retry = next(item for item in attempts if item.spec.parent_attempt_id is not None)

    assert status == RunStatus.SUCCEEDED
    assert len(attempts) == 2
    assert first.state.status.value == "failed"
    assert first.state.safe_to_retry is True
    assert retry.spec.parent_attempt_id == first.spec.attempt_id
    assert retry.spec.attempt_id != first.spec.attempt_id
    assert retry.slot_id == first.slot_id


@pytest.mark.asyncio
async def test_retry_budget_stops_after_configured_attempt_count(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "retry-budget")

    def factory(_spec):
        return AttemptScript(
            events=(),
            start_failure=ScriptedFailure(
                failure_class=FailureClass.PROVIDER_TRANSIENT,
                summary="still unavailable",
                safe_to_retry=True,
            ),
        )

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=factory)
    status = await coordinator.run_until_stalled("retry-budget")
    attempts = ledger.list_attempts("retry-budget", "review")
    first = next(item for item in attempts if item.spec.parent_attempt_id is None)
    retry = next(item for item in attempts if item.spec.parent_attempt_id is not None)

    assert status == RunStatus.FAILED
    assert len(attempts) == 2
    assert retry.spec.parent_attempt_id == first.spec.attempt_id


@pytest.mark.asyncio
async def test_failure_outside_profile_retry_policy_is_not_retried(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "nonretryable-run")
    coordinator, _backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda _spec: AttemptScript(
            events=(),
            start_failure=ScriptedFailure(
                failure_class=FailureClass.CONFIGURATION,
                summary="invalid fake backend setup",
                safe_to_retry=True,
            ),
        ),
    )

    status = await coordinator.run_until_stalled("nonretryable-run")

    assert status == RunStatus.FAILED
    assert len(ledger.list_attempts("nonretryable-run", "review")) == 1


@pytest.mark.asyncio
async def test_successful_elastic_sibling_is_retained_while_another_slot_retries(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    run_id = "feature-sibling"
    _create_run(
        ledger,
        app_config,
        "feature",
        run_id,
        overrides=RunOverrides(worker_counts={"implement": 2}),
    )
    failing_first_attempt = str(uuid5(NAMESPACE_URL, f"{run_id}/implement/implement/slot-01/1"))

    def factory(spec):
        if spec.attempt_id == failing_first_attempt:
            return AttemptScript(
                events=(),
                start_failure=ScriptedFailure(
                    failure_class=FailureClass.PROVIDER_TRANSIENT,
                    summary="slot one transient start failure",
                    safe_to_retry=True,
                ),
            )
        return _worker_script(spec)

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=factory)
    status = await coordinator.run_until_stalled(run_id)
    attempts = ledger.list_attempts(run_id, "implement")
    successful_slots = {
        item.slot_id
        for item in attempts
        if item.state.status.value == "succeeded"
        and item.result is not None
        and item.result.result is not None
    }

    assert status == RunStatus.SUCCEEDED
    assert len(attempts) == 3
    assert successful_slots == {"implement/slot-01", "implement/slot-02"}
    retry = next(item for item in attempts if item.spec.parent_attempt_id is not None)
    parent = next(item for item in attempts if item.spec.attempt_id == retry.spec.parent_attempt_id)
    assert retry.slot_id == parent.slot_id == "implement/slot-01"


@pytest.mark.asyncio
async def test_blocked_report_requires_attention_and_releases_settled_capacity(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "blocked-run")

    def blocked(spec):
        event = _worker_script(spec, statuses={"review": OutputStatus.BLOCKED}).events[0]
        return AttemptScript(
            events=(
                event.model_copy(
                    update={"result": event.result.model_copy(update={"artifacts": ()})}
                ),
            )
        )

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=blocked)

    status = await coordinator.run_until_stalled("blocked-run")
    run = ledger.get_run("blocked-run")

    assert status == RunStatus.ATTENTION_REQUIRED
    assert run.stages[0].status == StageStatus.BLOCKED
    assert ledger.list_attempts("blocked-run")[0].result.result.status == OutputStatus.BLOCKED
    assert all(item.status.value == "released" for item in ledger.list_reservations("blocked-run"))


@pytest.mark.asyncio
async def test_invalid_output_fails_stage_and_persists_invalid_result(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "invalid-run")

    def malformed(spec):
        script = _worker_script(spec)
        event = script.events[0]
        bad_result = event.result.model_copy(update={"input_revision": "stale-input"})
        return AttemptScript(
            events=(
                WorkerTerminalEvent(
                    kind="terminal",
                    attempt_id=event.attempt_id,
                    sequence=event.sequence,
                    result=bad_result,
                ),
            )
        )

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=malformed)
    status = await coordinator.run_until_stalled("invalid-run")
    attempt = ledger.list_attempts("invalid-run", "review")[0]

    assert status == RunStatus.FAILED
    assert attempt.result is not None
    assert attempt.result.validation_error is not None
    assert attempt.state.error_class.value == "invalid_output"


@pytest.mark.asyncio
async def test_wrong_terminal_attempt_identity_is_recorded_as_invalid_output(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "wrong-identity")

    def malformed(spec):
        event = _worker_script(spec).events[0]
        return AttemptScript(events=(event.model_copy(update={"attempt_id": "other-attempt"}),))

    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=malformed)
    status = await coordinator.run_until_stalled("wrong-identity")
    attempt = ledger.list_attempts("wrong-identity", "review")[0]

    assert status == RunStatus.FAILED
    assert attempt.state.error_class == FailureClass.INVALID_OUTPUT
    assert attempt.result is not None and attempt.result.validation_error is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("global_cap", "project_cap", "limited_scope"),
    [(1, 4, "global"), (4, 1, "project")],
)
async def test_competing_runs_obey_global_and_project_admission_caps(
    tmp_path, app_config, ledger_owner, global_cap, project_cap, limited_scope
) -> None:
    ledger, ownership = ledger_owner
    project = app_config.project.model_copy(update={"max_parallelism": project_cap})
    run_a, run_b = f"{limited_scope}-a", f"{limited_scope}-b"
    _create_run(ledger, app_config, "review", run_a, project=project)
    _create_run(ledger, app_config, "review", run_b, project=project)
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=_worker_script,
        auto_release=False,
        cap=global_cap,
    )

    coordinator.advance(run_a)
    coordinator.advance(run_a)
    await coordinator.dispatch_pending(run_a)
    coordinator.advance(run_b)
    coordinator.advance(run_b)
    assert ledger.list_attempts(run_b) == ()
    assert (
        sum(
            item.scope == limited_scope and item.status.value == "held"
            for item in ledger.list_reservations()
        )
        == 1
    )

    first_attempt = ledger.list_attempts(run_a)[0]
    await backend.wait_until_waiting(first_attempt.spec.attempt_id, 0)
    backend.release_next(first_attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    coordinator.advance(run_a)
    assert ledger.get_run(run_a).state.status == RunStatus.SUCCEEDED

    coordinator.advance(run_b)
    await coordinator.dispatch_pending(run_b)
    second_attempt = ledger.list_attempts(run_b)[0]
    await backend.wait_until_waiting(second_attempt.spec.attempt_id, 0)
    backend.release_next(second_attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    coordinator.advance(run_b)
    assert ledger.get_run(run_b).state.status == RunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_run_cap_serializes_ready_feature_checks(tmp_path, app_config, ledger_owner) -> None:
    ledger, ownership = ledger_owner
    feature = next(item for item in app_config.workflows if item.id == "feature")
    serial_feature = feature.model_copy(update={"max_parallelism": 1})
    _create_run(ledger, app_config, "feature", "run-cap", workflow=serial_feature)

    def factory(spec):
        script = _worker_script(spec)
        return AttemptScript(
            events=script.events,
            event_barrier=spec.stage_id in {"review", "test"},
        )

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=True
    )
    running = asyncio.create_task(coordinator.run_until_stalled("run-cap"))
    review_attempt_id = await backend.wait_until_started_stage("review")
    await backend.wait_until_waiting(review_attempt_id, 0)

    active = [
        item
        for item in ledger.list_attempts("run-cap")
        if item.state.status.value in {"launching", "running"}
    ]
    assert len(active) == 1
    assert (
        sum(
            item.scope == "run" and item.status.value == "held"
            for item in ledger.list_reservations("run-cap")
        )
        == 1
    )
    backend.release_next(active[0].spec.attempt_id)

    test_attempt_id = await backend.wait_until_started_stage("test")
    await backend.wait_until_waiting(test_attempt_id, 0)
    active = [
        item
        for item in ledger.list_attempts("run-cap")
        if item.state.status.value in {"launching", "running"}
    ]
    assert len(active) == 1
    backend.release_next(active[0].spec.attempt_id)
    assert await running == RunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_outbox_and_reservation_commit_precedes_fake_start_acknowledgement(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "outbox-run")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            start_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("outbox-run")
    coordinator.advance("outbox-run")
    dispatch = asyncio.create_task(coordinator.dispatch_pending("outbox-run"))
    attempt = ledger.list_attempts("outbox-run")[0]
    await backend.wait_until_start_waiting(attempt.spec.attempt_id)

    assert attempt.state.status.value == "launching"
    assert len(ledger.list_reservations("outbox-run")) == 4
    assert ledger.list_outbox_actions("outbox-run")[0].status.value == "claimed"
    assert backend.start_calls == [attempt.spec.attempt_id]

    backend.release_start(attempt.spec.attempt_id)
    assert await dispatch == 1
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status.value == "running"
    assert ledger.list_outbox_actions("outbox-run")[0].status.value == "acknowledged"
    assert await coordinator.dispatch_pending("outbox-run") == 0
    assert backend.start_calls == [attempt.spec.attempt_id]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)
    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    coordinator.advance("outbox-run")
    assert ledger.get_run("outbox-run").state.status == RunStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_unknown_start_outcome_is_not_retried_and_keeps_reservations(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "unknown-run")

    class UnknownLaunchBackend(FakeBackend):
        async def start(self, spec):
            raise RuntimeError("connection dropped after launch request")

    clock = FakeClock(origin=STAMP)
    backend = UnknownLaunchBackend(backend_id="codex", clock=clock)
    coordinator = ExecutionCoordinator(ledger, backend, ownership, clock=clock)
    coordinator.advance("unknown-run")
    coordinator.advance("unknown-run")

    await coordinator.dispatch_pending("unknown-run")

    attempts = ledger.list_attempts("unknown-run")
    assert len(attempts) == 1
    assert attempts[0].state.status.value == "outcome_unknown"
    assert ledger.get_run("unknown-run").state.status == RunStatus.ATTENTION_REQUIRED
    assert any(item.status.value == "held" for item in ledger.list_reservations("unknown-run"))
    assert all(item.status.value != "pending" for item in ledger.list_outbox_actions("unknown-run"))


@pytest.mark.asyncio
async def test_fake_clock_timeout_is_classified_and_releases_only_after_settlement(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    spec = _create_run(ledger, app_config, "review", "timeout-run")
    coordinator, backend, clock = _coordinator(
        ledger,
        ownership,
        factory=lambda worker: AttemptScript(
            events=_worker_script(worker).events,
            event_barrier=True,
        ),
        auto_release=True,
    )
    coordinator.advance("timeout-run")
    coordinator.advance("timeout-run")
    await coordinator.dispatch_pending("timeout-run")
    attempt = ledger.list_attempts("timeout-run")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)
    profile = next(item for item in spec.profiles if item.id == attempt.spec.profile_id)

    clock.advance(profile.timeout_seconds)
    await coordinator.wait_for_workers()
    timed_out = ledger.get_attempt(attempt.spec.attempt_id)

    assert timed_out.state.status.value == "timed_out"
    assert timed_out.state.error_class == FailureClass.TIMEOUT
    assert all(item.status.value == "released" for item in ledger.list_reservations("timeout-run"))
    coordinator.advance("timeout-run")
    assert ledger.get_run("timeout-run").state.status == RunStatus.FAILED


def test_fixed_select_one_and_elastic_slots_are_frozen_in_the_run_snapshot(
    tmp_path, app_config
) -> None:
    project, default_spec = _resolved_run(app_config, "research")
    default_run_path = tmp_path / "default.sqlite3"
    with SQLiteLedger(default_run_path) as ledger:
        ledger.create_run(
            "elastic-min", project, default_spec, uuid4(), actor="test", occurred_at=STAMP
        )
        assert resolve_stage_slots(
            ledger.get_run("elastic-min"),
            next(stage for stage in default_spec.workflow.stages if stage.id == "research"),
        ) == (("research/slot-01", "researcher"), ("research/slot-02", "researcher"))

    project, max_spec = _resolved_run(
        app_config,
        "research",
        overrides=RunOverrides(worker_counts={"research": 3}),
    )
    max_path = tmp_path / "elastic-max.sqlite3"
    with SQLiteLedger(max_path) as ledger:
        ledger.create_run(
            "elastic-max", project, max_spec, uuid4(), actor="test", occurred_at=STAMP
        )
    with SQLiteLedger(max_path) as reopened:
        persisted = reopened.get_run("elastic-max")
        research_stage = next(
            stage for stage in persisted.spec.workflow.stages if stage.id == "research"
        )
        assert len(resolve_stage_slots(persisted, research_stage)) == 3

    project, selected_spec = _resolved_run(
        app_config,
        "prototype",
        overrides=RunOverrides(profile_selections={"implement": "implementer"}),
    )
    prototype_run_path = tmp_path / "select-one.sqlite3"
    with SQLiteLedger(prototype_run_path) as ledger:
        ledger.create_run(
            "select-one", project, selected_spec, uuid4(), actor="test", occurred_at=STAMP
        )
        run = ledger.get_run("select-one")
        implement = next(stage for stage in run.spec.workflow.stages if stage.id == "implement")
        assert resolve_stage_slots(run, implement) == (("implement/slot-01", "implementer"),)


def test_legacy_resolved_workflow_without_policy_defaults_fail_closed(app_config) -> None:
    _project, spec = _resolved_run(app_config, "review")
    payload = spec.workflow.model_dump(mode="json")
    payload.pop("policy")

    legacy_workflow = ResolvedWorkflow.model_validate(payload)

    assert legacy_workflow.policy.allowed_backends == ()
    assert legacy_workflow.policy.allow_retry is False


def test_required_upstream_input_blocks_until_its_stage_has_persisted_output(
    tmp_path, app_config
) -> None:
    ledger = SQLiteLedger(tmp_path / "input-gate.sqlite3")
    try:
        project, spec = _resolved_run(app_config, "prototype")
        ledger.create_run("input-gate", project, spec, uuid4(), actor="test", occurred_at=STAMP)
        run = ledger.get_run("input-gate")
        stage = next(item for item in run.spec.workflow.stages if item.id == "implement")

        with pytest.raises(InputResolutionError, match="plan.plan is unavailable"):
            resolve_stage_inputs(run, stage)
    finally:
        ledger.close()


@pytest.mark.asyncio
async def test_claimed_launch_is_quarantined_after_coordinator_restart(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, old_ownership = ledger_owner
    _create_run(ledger, app_config, "review", "restart-run")
    old_coordinator, backend, clock = _coordinator(ledger, old_ownership, factory=_worker_script)
    old_coordinator.advance("restart-run")
    old_coordinator.advance("restart-run")
    claimed = ledger.claim_next_outbox("old-owner", STAMP, run_id="restart-run")
    assert claimed is not None
    assert backend.start_calls == []

    old_ownership.release(STAMP)
    new_ownership = CoordinatorOwnership(ledger, tmp_path / "coordinator.lock")
    new_ownership.acquire("new-owner", STAMP)
    try:
        new_backend = FakeBackend(backend_id="codex", script_factory=_worker_script, clock=clock)
        restarted = ExecutionCoordinator(ledger, new_backend, new_ownership, clock=clock)
        assert restarted.mark_claimed_launches_unknown("restart-run") == 1
        assert await restarted.dispatch_pending("restart-run") == 0
        assert ledger.get_run("restart-run").state.status == RunStatus.ATTENTION_REQUIRED
        assert ledger.list_attempts("restart-run")[0].state.status.value == "outcome_unknown"
        assert new_backend.start_calls == []
    finally:
        new_ownership.release(STAMP)
