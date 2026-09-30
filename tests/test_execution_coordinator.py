from __future__ import annotations

import asyncio
import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from orchestrator.backends.fake import (
    AttemptScript,
    FakeBackend,
    FakeClock,
    ScriptedAck,
    ScriptedFailure,
)
from orchestrator.backends.fake_decision import DecisionBarrier, FakeDecisionEngine
from orchestrator.domain.backend import (
    ArtifactEntry,
    OutputStatus,
    Reconciliation,
    ShutdownReceipt,
    WorkerResult,
    WorkerTerminalEvent,
)
from orchestrator.domain.decisions import (
    DecisionDispositionReason,
    DecisionDispositionStatus,
    DecisionEngineFailure,
    DecisionResult,
    DecisionResultClass,
)
from orchestrator.domain.models import (
    AttemptStatus,
    Effort,
    FailureClass,
    InterventionKind,
    ModelBindingSettings,
    PauseIntervention,
    RedirectIntervention,
    ResolvedWorkflow,
    ResumeIntervention,
    RetryIntervention,
    RunOverrides,
    RunStatus,
    StageStatus,
    SteerIntervention,
    StopAttemptIntervention,
    StopIntervention,
    WorkflowPreset,
)
from orchestrator.execution import (
    ExecutionCoordinator,
    InputResolutionError,
    resolve_stage_inputs,
    resolve_stage_slots,
)
from orchestrator.persistence import CoordinatorOwnership, SQLiteLedger
from orchestrator.persistence.ledger import canonical_json, content_hash
from orchestrator.persistence.models import (
    CommandOutcome,
    ControlDeliveryStatus,
    LedgerMutation,
    RunProjectionUpdate,
    StageResult,
    StageUpdate,
)
from orchestrator.resolution import resolve_run
from orchestrator.validation import validate_application

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


def _coordinator(ledger, ownership, *, factory, auto_release=True, cap=4, decision_engine=None):
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
            decision_engine=decision_engine,
        ),
        backend,
        clock,
    )


def _complete_plan_before_decision(ledger, run_id: str, *, include_output: bool = True) -> None:
    run = ledger.get_run(run_id)
    outputs = (
        (
            ArtifactEntry(
                name="plan",
                schema_id="plan-v1",
                content_hash="a" * 64,
            ),
        )
        if include_output
        else ()
    )
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id=run_id,
            expected_revision=run.state.revision,
            actor="test",
            occurred_at=STAMP,
            run_update=RunProjectionUpdate(status=RunStatus.RUNNING),
            stage_updates=(
                StageUpdate(
                    stage_id="plan",
                    status=StageStatus.SUCCEEDED,
                    result=StageResult(outputs=outputs),
                ),
            ),
        )
    )


def _decision_result(request, *, outcome_id="implementer", abstained=False):
    return DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=request.current_run_revision,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id=None if abstained else outcome_id,
        abstained=abstained,
        abstention_reason="The declared evidence does not distinguish the choices."
        if abstained
        else None,
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
async def test_bounded_decision_is_persisted_before_redirect_and_reused_after_restart(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "decision-accepted")
    engine = FakeDecisionEngine((lambda request: _decision_result(request),))
    coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=engine
    )

    status = await coordinator.run_until_stalled("decision-accepted")

    assert status == RunStatus.SUCCEEDED
    assert len(engine.requests) == 1
    record = ledger.list_decision_records("decision-accepted")[0]
    assert record.request.allowed_outcomes[0].outcome_id == "prototype-implementer"
    assert record.request.allowed_outcomes[1].outcome_id == "implementer"
    assert tuple(item.source_ref for item in record.request.evidence) == (
        "run.task",
        "plan.plan",
    )
    assert record.disposition is not None
    assert record.disposition.status == DecisionDispositionStatus.ACCEPTED
    assert record.disposition.selected_outcome_id == "implementer"
    assert ledger.get_stage_redirect("decision-accepted", "implement") == "implementer"
    implement = ledger.list_attempts("decision-accepted", "implement")
    assert len(implement) == 1
    assert implement[0].spec.profile_id == "implementer"
    decision_kinds = [
        event.kind.value
        for event in ledger.list_events("decision-accepted")
        if event.kind.value.startswith("decision_")
    ]
    assert decision_kinds == [
        "decision_requested",
        "decision_inference_started",
        "decision_result_recorded",
        "decision_policy_evaluated",
        "decision_accepted",
    ]

    restarted_engine = FakeDecisionEngine()
    restarted, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=restarted_engine
    )
    assert await restarted.run_until_stalled("decision-accepted") == RunStatus.SUCCEEDED
    assert restarted_engine.requests == []


@pytest.mark.asyncio
async def test_question_ids_do_not_collide_with_other_stage_ids(app_config, ledger_owner):
    ledger, ownership = ledger_owner
    data = next(item for item in app_config.workflows if item.id == "prototype").model_dump()
    question = data["policy"]["decision_questions"][0]
    later_question = dict(question, question_id="implement", stage_id="handoff")
    data["policy"]["decision_questions"] = [later_question, question]
    data["allowed_redirects"].append({"stage": "handoff", "allowed_profiles": ["handoff"]})
    handoff = next(stage for stage in data["stages"] if stage["id"] == "handoff")
    handoff["slot_kind"] = "select_one"
    workflow = WorkflowPreset.model_validate(data)
    validate_application(app_config.agents, [workflow], app_config.backends)
    _create_run(ledger, app_config, "prototype", "question-collision", workflow=workflow)

    def first_allowed(request):
        return _decision_result(request, outcome_id=request.allowed_outcomes[0].outcome_id)

    engine = FakeDecisionEngine((first_allowed, first_allowed))
    coordinator, _backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=_worker_script,
        decision_engine=engine,
    )
    assert await coordinator.run_until_stalled("question-collision") == RunStatus.SUCCEEDED
    assert [request.question_id for request in engine.requests] == [
        "implementer_choice",
        "implement",
    ]
    assert [request.allowed_outcomes[0].outcome_id for request in engine.requests] == [
        "prototype-implementer",
        "handoff",
    ]


@pytest.mark.asyncio
async def test_explicit_profile_selection_is_preserved_without_semantic_rerouting(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(
        ledger,
        app_config,
        "prototype",
        "decision-user-selected-default",
        overrides=RunOverrides(profile_selections={"implement": "prototype-implementer"}),
    )
    engine = FakeDecisionEngine()
    coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=engine
    )

    assert await coordinator.run_until_stalled("decision-user-selected-default") == (
        RunStatus.SUCCEEDED
    )
    assert engine.requests == []
    assert ledger.list_decision_records("decision-user-selected-default") == ()
    implement = ledger.list_attempts("decision-user-selected-default", "implement")
    assert len(implement) == 1
    assert implement[0].spec.profile_id == "prototype-implementer"


@pytest.mark.asyncio
async def test_abstention_and_engine_failure_follow_declared_attention_policy(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "decision-abstained")
    abstaining_engine = FakeDecisionEngine(
        (lambda request: _decision_result(request, abstained=True),)
    )
    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=abstaining_engine
    )

    assert await coordinator.run_until_stalled("decision-abstained") == RunStatus.ATTENTION_REQUIRED
    abstained = ledger.list_decision_records("decision-abstained")[0]
    assert abstained.disposition is not None
    assert abstained.disposition.status == DecisionDispositionStatus.ABSTAINED
    assert abstained.disposition.reason == DecisionDispositionReason.EXPLICIT_ABSTENTION
    assert ledger.get_stage_redirect("decision-abstained", "implement") is None
    assert len(backend.start_calls) == 1  # only the plan stage ran

    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0]
    fallback_policy = question.acceptance_policy.model_copy(
        update={
            "on_abstention": "fallback",
            "fallback_outcome_id": "prototype-implementer",
        }
    )
    fallback_question = question.model_copy(update={"acceptance_policy": fallback_policy})
    fallback_workflow = prototype.model_copy(
        update={
            "policy": prototype.policy.model_copy(
                update={"decision_questions": [fallback_question]}
            )
        }
    )
    _create_run(
        ledger,
        app_config,
        "prototype",
        "decision-fallback",
        workflow=fallback_workflow,
    )
    fallback_engine = FakeDecisionEngine(
        (lambda request: _decision_result(request, abstained=True),)
    )
    fallback_coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=fallback_engine
    )
    assert await fallback_coordinator.run_until_stalled("decision-fallback") == (
        RunStatus.SUCCEEDED
    )
    fallback = ledger.list_decision_records("decision-fallback")[0]
    assert fallback.disposition is not None
    assert fallback.disposition.status == DecisionDispositionStatus.FALLBACK
    assert fallback.disposition.selected_outcome_id == "prototype-implementer"
    assert ledger.get_stage_redirect("decision-fallback", "implement") == ("prototype-implementer")

    _create_run(ledger, app_config, "prototype", "decision-engine-failed")
    failed_engine = FakeDecisionEngine(
        (
            lambda request: DecisionEngineFailure(
                decision_id=request.decision_id,
                classification="engine_error",
                detail="scripted failure",
            ),
        )
    )
    failed_coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=failed_engine
    )
    assert await failed_coordinator.run_until_stalled("decision-engine-failed") == (
        RunStatus.ATTENTION_REQUIRED
    )
    failed = ledger.list_decision_records("decision-engine-failed")[0]
    assert failed.failure is not None
    assert failed.disposition is not None
    assert failed.disposition.status == DecisionDispositionStatus.ATTENTION_REQUIRED

    _create_run(ledger, app_config, "prototype", "decision-disallowed")
    disallowed_engine = FakeDecisionEngine(
        (lambda request: _decision_result(request, outcome_id="reviewer"),)
    )
    disallowed_coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=disallowed_engine
    )
    assert await disallowed_coordinator.run_until_stalled("decision-disallowed") == (
        RunStatus.ATTENTION_REQUIRED
    )
    disallowed = ledger.list_decision_records("decision-disallowed")[0]
    assert disallowed.disposition is not None
    assert disallowed.disposition.status == DecisionDispositionStatus.REJECTED
    assert disallowed.disposition.reason == DecisionDispositionReason.DISALLOWED_OUTCOME
    assert ledger.list_attempts("decision-disallowed", "implement") == ()

    _create_run(ledger, app_config, "prototype", "decision-malformed")
    malformed_engine = FakeDecisionEngine(
        (
            lambda request: DecisionResult(
                decision_id=request.decision_id,
                effective_inference=request.inference_binding,
                consumed_run_revision=request.current_run_revision,
                consumed_evidence_digest=request.evidence_digest,
                result_class=DecisionResultClass.MALFORMED,
            ),
        )
    )
    malformed_coordinator, _backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=malformed_engine
    )
    assert await malformed_coordinator.run_until_stalled("decision-malformed") == (
        RunStatus.ATTENTION_REQUIRED
    )
    malformed = ledger.list_decision_records("decision-malformed")[0]
    assert malformed.disposition is not None
    assert malformed.disposition.reason == DecisionDispositionReason.MALFORMED_RESULT


@pytest.mark.asyncio
async def test_missing_required_decision_evidence_fails_closed_without_engine_call(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "decision-missing-evidence")
    _complete_plan_before_decision(ledger, "decision-missing-evidence", include_output=False)
    engine = FakeDecisionEngine()
    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=engine
    )

    assert await coordinator.run_until_stalled("decision-missing-evidence") == (
        RunStatus.ATTENTION_REQUIRED
    )
    record = ledger.list_decision_records("decision-missing-evidence")[0]
    assert record.request.missing_evidence_refs == ("plan.plan",)
    assert record.failure is not None
    assert record.failure.classification.value == "missing_evidence"
    assert record.disposition is not None
    assert record.disposition.reason == DecisionDispositionReason.MISSING_EVIDENCE
    assert engine.requests == []
    assert backend.start_calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_kind", ["result", "failure"])
async def test_wrong_decision_identity_is_durably_rejected(app_config, ledger_owner, reply_kind):
    ledger, ownership = ledger_owner
    run_id = f"wrong-decision-{reply_kind}"
    _create_run(ledger, app_config, "prototype", run_id)

    def wrong_reply(request):
        if reply_kind == "result":
            return _decision_result(request).model_copy(update={"decision_id": uuid4()})
        return DecisionEngineFailure(
            decision_id=uuid4(),
            classification="engine_error",
            detail="Wrong request.",
        )

    engine = FakeDecisionEngine((wrong_reply,))
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=_worker_script,
        decision_engine=engine,
    )
    assert await coordinator.run_until_stalled(run_id) == RunStatus.ATTENTION_REQUIRED
    record = ledger.list_decision_records(run_id)[0]
    assert record.disposition.reason == DecisionDispositionReason.INCOMPATIBLE_RESULT
    assert record.completed_at is not None
    assert ledger.get_stage_redirect(run_id, "implement") is None
    assert len(backend.start_calls) == 1  # Only the prerequisite planner ran.
    assert await coordinator.run_until_stalled(run_id) == RunStatus.ATTENTION_REQUIRED
    assert len(engine.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("reply_kind", ["raw", "invalid_model", "incompatible"])
async def test_malformed_engine_reply_never_dispatches_failure_fallback(
    app_config,
    ledger_owner,
    reply_kind,
):
    ledger, ownership = ledger_owner
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0]
    question = question.model_copy(
        update={
            "acceptance_policy": question.acceptance_policy.model_copy(
                update={"on_engine_failure": "fallback", "fallback_outcome_id": "implementer"},
            )
        }
    )
    workflow = prototype.model_copy(
        update={
            "policy": prototype.policy.model_copy(update={"decision_questions": [question]}),
        }
    )
    _create_run(ledger, app_config, "prototype", "invalid-fallback", workflow=workflow)

    def invalid_reply(request):
        if reply_kind == "raw":
            return {"outcome_id": "implementer"}
        if reply_kind == "invalid_model":
            return _decision_result(request).model_copy(update={"outcome_id": None})
        return DecisionEngineFailure(
            decision_id=request.decision_id,
            classification="incompatible_result",
            detail="Bad schema.",
        )

    engine = FakeDecisionEngine((invalid_reply,))
    coordinator, _backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=_worker_script,
        decision_engine=engine,
    )
    assert await coordinator.run_until_stalled("invalid-fallback") == RunStatus.ATTENTION_REQUIRED
    record = ledger.list_decision_records("invalid-fallback")[0]
    assert record.disposition.status == DecisionDispositionStatus.REJECTED
    assert record.failure is not None
    assert ledger.list_attempts("invalid-fallback", "implement") == ()
    assert ledger.get_stage_redirect("invalid-fallback", "implement") is None


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", ["accepted", "abstained", "fallback", "pending"])
async def test_decision_crash_boundaries_reopen_without_reinference(app_config, tmp_path, outcome):
    path = tmp_path / "decision-restart.sqlite3"
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0]
    if outcome == "fallback":
        question = question.model_copy(
            update={
                "acceptance_policy": question.acceptance_policy.model_copy(
                    update={
                        "on_abstention": "fallback",
                        "fallback_outcome_id": "implementer",
                    }
                ),
            }
        )
    workflow = prototype.model_copy(
        update={
            "policy": prototype.policy.model_copy(update={"decision_questions": [question]}),
        }
    )
    with SQLiteLedger(path) as ledger:
        ownership = CoordinatorOwnership(ledger, tmp_path / "restart.lock")
        ownership.acquire("before-restart", STAMP)
        try:
            _create_run(ledger, app_config, "prototype", "restart", workflow=workflow)
            _complete_plan_before_decision(ledger, "restart")

            def infer(request):
                # A second connection must see the request before the engine responds.
                with SQLiteLedger(path) as observer:
                    assert observer.get_decision_record(request.decision_id).request == request
                return _decision_result(request, abstained=outcome in {"abstained", "fallback"})

            barrier = DecisionBarrier() if outcome == "pending" else None
            engine = FakeDecisionEngine((infer,), barrier=barrier)
            coordinator, backend, _clock = _coordinator(
                ledger,
                ownership,
                factory=_worker_script,
                decision_engine=engine,
            )
            task = asyncio.create_task(coordinator._process_ready_decisions("restart"))
            if barrier is not None:
                await barrier.entered.wait()
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert await task
            saved = ledger.list_decision_records("restart")[0]
            assert backend.start_calls == []
            assert len(engine.requests) == 1
        finally:
            ownership.release(STAMP)

    with SQLiteLedger(path) as ledger:
        ownership = CoordinatorOwnership(ledger, tmp_path / "restart.lock")
        ownership.acquire("after-restart", STAMP)
        try:
            assert ledger.list_decision_records("restart") == (saved,)
            engine = FakeDecisionEngine()
            coordinator, backend, _clock = _coordinator(
                ledger,
                ownership,
                factory=_worker_script,
                decision_engine=engine,
            )
            expected = (
                RunStatus.SUCCEEDED
                if outcome in {"accepted", "fallback"}
                else RunStatus.ATTENTION_REQUIRED
            )
            assert await coordinator.run_until_stalled("restart") == expected
            record = ledger.list_decision_records("restart")[0]
            assert record.request == saved.request
            assert record.completed_at is not None
            if outcome != "pending":
                assert record == saved
            else:
                assert record.failure.classification.value == "engine_unavailable"
            assert engine.requests == []
            launches = list(backend.start_calls)
            revision = ledger.get_run("restart").state.revision
            assert await coordinator.run_until_stalled("restart") == expected
            assert ledger.get_run("restart").state.revision == revision
            assert backend.start_calls == launches
        finally:
            ownership.release(STAMP)


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", [None, "repair_not_needed", "repair_needed"])
async def test_restarted_conditional_decision_requires_an_active_branch(
    app_config, tmp_path, branch
):
    feature = next(item for item in app_config.workflows if item.id == "feature").model_dump()
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0].model_dump()
    question.update(stage_id="repair", evidence_requirements=[question["evidence_requirements"][0]])
    feature["policy"].update(allow_profile_selection=True, decision_questions=[question])
    feature["allowed_redirects"] = [{"stage": "repair", "allowed_profiles": ["implementer"]}]
    next(stage for stage in feature["stages"] if stage["id"] == "repair")["slot_kind"] = (
        "select_one"
    )
    workflow = WorkflowPreset.model_validate(feature)
    validate_application(app_config.agents, [workflow], app_config.backends)
    path = tmp_path / "conditional.sqlite3"
    with SQLiteLedger(path) as ledger:
        _create_run(ledger, app_config, "feature", "conditional", workflow=workflow)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="conditional",
                expected_revision=0,
                actor="test",
                occurred_at=STAMP,
                run_update=RunProjectionUpdate(status=RunStatus.RUNNING),
                stage_updates=(
                    StageUpdate(
                        stage_id="repair_gate",
                        status=StageStatus.SUCCEEDED,
                        result=StageResult(decision=branch),
                    ),
                ),
            )
        )
    with SQLiteLedger(path) as ledger:
        ownership = CoordinatorOwnership(ledger, tmp_path / "conditional.lock")
        ownership.acquire("restarted", STAMP)
        try:
            engine = FakeDecisionEngine((lambda request: _decision_result(request),))
            coordinator, backend, _clock = _coordinator(
                ledger,
                ownership,
                factory=_worker_script,
                decision_engine=engine,
            )
            assert await coordinator._process_ready_decisions("conditional") == (
                branch == "repair_needed"
            )
            assert len(engine.requests) == (1 if branch == "repair_needed" else 0)
            assert len(ledger.list_decision_records("conditional")) == len(engine.requests)
            assert backend.start_calls == []
        finally:
            ownership.release(STAMP)


@pytest.mark.asyncio
async def test_run_revision_change_while_decision_engine_waits_rejects_result(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "decision-stale")
    _complete_plan_before_decision(ledger, "decision-stale")
    barrier = DecisionBarrier()
    engine = FakeDecisionEngine((lambda request: _decision_result(request),), barrier=barrier)
    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=_worker_script, decision_engine=engine
    )
    task = asyncio.create_task(coordinator.run_until_stalled("decision-stale"))
    await barrier.entered.wait()
    current = ledger.get_run("decision-stale")
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id="decision-stale",
            expected_revision=current.state.revision,
            actor="test",
            occurred_at=STAMP,
            run_update=RunProjectionUpdate(elapsed_seconds=current.state.elapsed_seconds + 1),
        )
    )
    barrier.release.set()

    assert await task == RunStatus.ATTENTION_REQUIRED
    record = ledger.list_decision_records("decision-stale")[0]
    assert record.disposition is not None
    assert record.disposition.status == DecisionDispositionStatus.REJECTED
    assert record.disposition.reason == DecisionDispositionReason.STALE_RUN_REVISION
    assert ledger.get_stage_redirect("decision-stale", "implement") is None
    assert backend.start_calls == []


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
async def test_late_start_ack_after_timeout_never_replays_or_releases_reservation(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "late-start")

    class LateStartBackend(FakeBackend):
        def __init__(self) -> None:
            super().__init__(
                backend_id="codex",
                script_factory=lambda spec: AttemptScript(
                    events=_worker_script(spec).events,
                    start_barrier=True,
                ),
                auto_release=False,
            )
            self.late_ack = None

        async def start(self, spec, *, preflight_record_id=None, preflight_record_hash=None):
            self.late_ack = asyncio.create_task(
                super().start(
                    spec,
                    preflight_record_id=preflight_record_id,
                    preflight_record_hash=preflight_record_hash,
                )
            )
            return await asyncio.shield(self.late_ack)

    backend = LateStartBackend()
    coordinator = ExecutionCoordinator(
        ledger,
        backend,
        ownership,
        clock=FakeClock(origin=STAMP),
        launch_timeout_seconds=0.01,
    )

    status = await coordinator.run_until_stalled("late-start")
    attempt = ledger.list_attempts("late-start")[0]
    assert status == RunStatus.ATTENTION_REQUIRED
    assert attempt.state.status == AttemptStatus.OUTCOME_UNKNOWN
    assert backend.late_ack is not None
    await backend.wait_until_start_waiting(attempt.spec.attempt_id)
    backend.release_start(attempt.spec.attempt_id)
    await backend.late_ack

    assert backend.start_calls == [attempt.spec.attempt_id]
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.OUTCOME_UNKNOWN
    assert any(item.status.value == "held" for item in ledger.list_reservations("late-start"))


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


@pytest.mark.asyncio
async def test_stale_control_is_persisted_as_rejected_and_pause_without_work_is_immediate(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "pause-empty")
    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=_worker_script)

    stale = await coordinator.apply_intervention(
        PauseIntervention(
            command_id=uuid4(),
            actor="user",
            target="pause-empty",
            expected_run_revision=9,
            kind=InterventionKind.PAUSE,
            run_id="pause-empty",
        )
    )
    assert stale.outcome == CommandOutcome.REJECTED
    assert "stale_revision" in (stale.reason or "")
    stale_record = ledger.list_intervention_records("pause-empty")[-1]
    assert stale_record.validation_outcome == "rejected"

    run = ledger.get_run("pause-empty")
    paused = await coordinator.apply_intervention(
        PauseIntervention(
            command_id=uuid4(),
            actor="user",
            target="pause-empty",
            expected_run_revision=run.state.revision,
            kind=InterventionKind.PAUSE,
            run_id="pause-empty",
        )
    )
    assert paused.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_run("pause-empty").state.status == RunStatus.PAUSED


@pytest.mark.asyncio
async def test_pause_drains_active_worker_and_resume_preserves_completed_work(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "pause-active")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("pause-active")
    coordinator.advance("pause-active")
    await coordinator.dispatch_pending("pause-active")
    attempt = ledger.list_attempts("pause-active")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)

    paused = await coordinator.apply_intervention(
        PauseIntervention(
            command_id=uuid4(),
            actor="user",
            target="pause-active",
            expected_run_revision=ledger.get_run("pause-active").state.revision,
            kind=InterventionKind.PAUSE,
            run_id="pause-active",
        )
    )
    assert paused.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_run("pause-active").state.status == RunStatus.PAUSE_REQUESTED
    assert len(ledger.list_attempts("pause-active")) == 1

    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    assert ledger.get_run("pause-active").state.status == RunStatus.PAUSED
    saved_result = ledger.get_attempt(attempt.spec.attempt_id).result
    assert saved_result is not None and saved_result.result is not None

    run = ledger.get_run("pause-active")
    resumed = await coordinator.apply_intervention(
        ResumeIntervention(
            command_id=uuid4(),
            actor="user",
            target="pause-active",
            expected_run_revision=run.state.revision,
            kind=InterventionKind.RESUME,
            run_id="pause-active",
        )
    )
    assert resumed.outcome == CommandOutcome.ACCEPTED
    assert await coordinator.run_until_stalled("pause-active") == RunStatus.SUCCEEDED
    assert ledger.get_attempt(attempt.spec.attempt_id).result == saved_result


@pytest.mark.asyncio
async def test_stop_selected_attempt_retains_attention_until_run_stop(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "stop-selected")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("stop-selected")
    coordinator.advance("stop-selected")
    await coordinator.dispatch_pending("stop-selected")
    attempt = ledger.list_attempts("stop-selected")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)

    stopped_attempt = await coordinator.apply_intervention(
        StopAttemptIntervention(
            command_id=uuid4(),
            actor="user",
            target=attempt.spec.attempt_id,
            expected_run_revision=ledger.get_run("stop-selected").state.revision,
            kind=InterventionKind.STOP_ATTEMPT,
            run_id="stop-selected",
            attempt_id=attempt.spec.attempt_id,
        )
    )
    assert stopped_attempt.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.CANCELLED
    assert ledger.get_run("stop-selected").state.status == RunStatus.ATTENTION_REQUIRED
    assert all(
        item.status.value == "released" for item in ledger.list_reservations("stop-selected")
    )
    record = ledger.list_intervention_records("stop-selected")[-1]
    assert record.delivery_state == ControlDeliveryStatus.ACKNOWLEDGED

    run = ledger.get_run("stop-selected")
    stopped = await coordinator.apply_intervention(
        StopIntervention(
            command_id=uuid4(),
            actor="user",
            target="stop-selected",
            expected_run_revision=run.state.revision,
            kind=InterventionKind.STOP,
            run_id="stop-selected",
        )
    )
    assert stopped.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_run("stop-selected").state.status == RunStatus.STOPPED
    await coordinator.wait_for_workers()


@pytest.mark.asyncio
async def test_workflow_stop_interrupts_active_worker_and_stops_after_close(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "stop-run")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("stop-run")
    coordinator.advance("stop-run")
    await coordinator.dispatch_pending("stop-run")
    attempt = ledger.list_attempts("stop-run")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)

    receipt = await coordinator.apply_intervention(
        StopIntervention(
            command_id=uuid4(),
            actor="user",
            target="stop-run",
            expected_run_revision=ledger.get_run("stop-run").state.revision,
            kind=InterventionKind.STOP,
            run_id="stop-run",
        )
    )
    assert receipt.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.CANCELLED
    assert ledger.get_run("stop-run").state.status == RunStatus.STOPPED
    assert all(item.status.value == "released" for item in ledger.list_reservations("stop-run"))
    await coordinator.wait_for_workers()


@pytest.mark.asyncio
async def test_unsupported_workflow_stop_retains_capacity_for_reconciliation(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "stop-unsupported")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            interrupt_acks=(
                ScriptedAck(accepted=False, supported=False, reason="interrupt unavailable"),
            ),
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("stop-unsupported")
    coordinator.advance("stop-unsupported")
    await coordinator.dispatch_pending("stop-unsupported")
    attempt = ledger.list_attempts("stop-unsupported")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)

    await coordinator.apply_intervention(
        StopIntervention(
            command_id=uuid4(),
            actor="user",
            target="stop-unsupported",
            expected_run_revision=ledger.get_run("stop-unsupported").state.revision,
            kind=InterventionKind.STOP,
            run_id="stop-unsupported",
        )
    )
    assert ledger.get_run("stop-unsupported").state.status == RunStatus.ATTENTION_REQUIRED
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.RUNNING
    assert any(item.status.value == "held" for item in ledger.list_reservations("stop-unsupported"))
    record = ledger.list_intervention_records("stop-unsupported")[-1]
    assert record.delivery_state == ControlDeliveryStatus.UNSUPPORTED
    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()


@pytest.mark.asyncio
async def test_worker_completion_wins_race_with_pending_interrupt(app_config, ledger_owner) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "stop-race")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            interrupt_acks=(ScriptedAck(barrier=True),),
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("stop-race")
    coordinator.advance("stop-race")
    await coordinator.dispatch_pending("stop-race")
    attempt = ledger.list_attempts("stop-race")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)
    run = ledger.get_run("stop-race")
    stopping = asyncio.create_task(
        coordinator.apply_intervention(
            StopAttemptIntervention(
                command_id=uuid4(),
                actor="user",
                target=attempt.spec.attempt_id,
                expected_run_revision=run.state.revision,
                kind=InterventionKind.STOP_ATTEMPT,
                run_id="stop-race",
                attempt_id=attempt.spec.attempt_id,
            )
        )
    )
    await backend.wait_until_control_waiting(attempt.spec.attempt_id, "interrupt")
    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    backend.release_control(attempt.spec.attempt_id, "interrupt")
    receipt = await stopping

    assert receipt.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.SUCCEEDED
    assert ledger.get_run("stop-race").state.status == RunStatus.SUCCEEDED
    record = next(
        item
        for item in ledger.list_intervention_records("stop-race")
        if item.command_id == receipt.command_id
    )
    assert record.delivery_state == ControlDeliveryStatus.REJECTED


@pytest.mark.asyncio
async def test_timeout_uses_persisted_interrupt_and_bounded_close(app_config, ledger_owner) -> None:
    ledger, ownership = ledger_owner
    workflow = next(item for item in app_config.workflows if item.id == "review")
    profile_id = next(item.default_profile for item in workflow.stages if item.id == "review")
    agents = app_config.agents.model_copy(
        update={
            "agents": [
                agent.model_copy(update={"timeout_seconds": 1}) if agent.id == profile_id else agent
                for agent in app_config.agents.agents
            ]
        }
    )
    _create_run(ledger, replace(app_config, agents=agents), "review", "timeout-run")
    coordinator, backend, clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            event_barrier=True,
        ),
        auto_release=False,
    )
    running = asyncio.create_task(coordinator.run_until_stalled("timeout-run"))
    attempt_id = await backend.wait_until_started_stage("review")
    await backend.wait_until_waiting(attempt_id, 0)
    clock.advance(1)

    assert await running == RunStatus.FAILED
    attempt = ledger.get_attempt(attempt_id)
    assert attempt.state.status == AttemptStatus.TIMED_OUT
    assert ledger.get_run("timeout-run").state.status == RunStatus.FAILED
    assert any(
        event.kind.value == "timeout_detected" for event in ledger.list_events("timeout-run")
    )
    intervention = ledger.list_intervention_records("timeout-run")[-1]
    assert intervention.kind == InterventionKind.STOP_ATTEMPT
    assert intervention.delivery_state == ControlDeliveryStatus.ACKNOWLEDGED


@pytest.mark.asyncio
async def test_timeout_with_unsettled_close_keeps_unknown_attempt_capacity(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    workflow = next(item for item in app_config.workflows if item.id == "review")
    profile_id = next(item.default_profile for item in workflow.stages if item.id == "review")
    agents = app_config.agents.model_copy(
        update={
            "agents": [
                agent.model_copy(update={"timeout_seconds": 1}) if agent.id == profile_id else agent
                for agent in app_config.agents.agents
            ]
        }
    )
    _create_run(ledger, replace(app_config, agents=agents), "review", "timeout-unknown")
    coordinator, backend, clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            close_receipts=(ShutdownReceipt(settled=False, detail="still running"),),
            reconciliations=(Reconciliation(known=False, detail="ownership unavailable"),),
            event_barrier=True,
        ),
        auto_release=False,
    )
    running = asyncio.create_task(coordinator.run_until_stalled("timeout-unknown"))
    attempt_id = await backend.wait_until_started_stage("review")
    await backend.wait_until_waiting(attempt_id, 0)
    clock.advance(1)

    assert await running == RunStatus.ATTENTION_REQUIRED
    assert ledger.get_attempt(attempt_id).state.status == AttemptStatus.OUTCOME_UNKNOWN
    assert any(item.status.value == "held" for item in ledger.list_reservations("timeout-unknown"))
    assert ledger.list_intervention_records("timeout-unknown")[-1].delivery_state == (
        ControlDeliveryStatus.UNKNOWN
    )


@pytest.mark.asyncio
async def test_steer_acknowledgement_changes_effective_input_revision(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "steer-run")

    def factory(spec):
        event = _worker_script(spec).events[0]
        result = event.result.model_copy(update={"input_revision": "effective"})
        return AttemptScript(
            events=(event.model_copy(update={"result": result}),),
            event_barrier=True,
        )

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance("steer-run")
    coordinator.advance("steer-run")
    await coordinator.dispatch_pending("steer-run")
    attempt = ledger.list_attempts("steer-run")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)
    original_revision = attempt.state.effective_input_revision

    receipt = await coordinator.apply_intervention(
        SteerIntervention(
            command_id=uuid4(),
            actor="user",
            target=attempt.spec.attempt_id,
            expected_run_revision=ledger.get_run("steer-run").state.revision,
            kind=InterventionKind.STEER,
            run_id="steer-run",
            attempt_id=attempt.spec.attempt_id,
            expected_turn_id=attempt.state.worker_turn_id,
            instruction="Prioritize security findings",
        )
    )
    assert receipt.outcome == CommandOutcome.ACCEPTED
    updated = ledger.get_attempt(attempt.spec.attempt_id)
    assert updated.state.effective_input_revision != original_revision
    assert updated.state.input_revision_uncertain is False
    assert ledger.list_intervention_records("steer-run")[-1].delivery_state == (
        ControlDeliveryStatus.ACKNOWLEDGED
    )

    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.SUCCEEDED


@pytest.mark.asyncio
async def test_result_from_pre_steer_input_cannot_satisfy_completion(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "review", "steer-stale-result")

    def factory(spec):
        event = _worker_script(spec).events[0]
        result = event.result.model_copy(update={"input_revision": "effective"})
        return AttemptScript(
            events=(event.model_copy(update={"result": result}),),
            steer_acks=(ScriptedAck(consumed=False),),
            event_barrier=True,
        )

    coordinator, backend, _clock = _coordinator(
        ledger, ownership, factory=factory, auto_release=False
    )
    coordinator.advance("steer-stale-result")
    coordinator.advance("steer-stale-result")
    await coordinator.dispatch_pending("steer-stale-result")
    attempt = ledger.list_attempts("steer-stale-result")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)
    await coordinator.apply_intervention(
        SteerIntervention(
            command_id=uuid4(),
            actor="user",
            target=attempt.spec.attempt_id,
            expected_run_revision=ledger.get_run("steer-stale-result").state.revision,
            kind=InterventionKind.STEER,
            run_id="steer-stale-result",
            attempt_id=attempt.spec.attempt_id,
            expected_turn_id=attempt.state.worker_turn_id,
            instruction="Prioritize security findings",
        )
    )
    backend.release_next(attempt.spec.attempt_id)
    await coordinator.wait_for_workers()
    assert ledger.get_attempt(attempt.spec.attempt_id).state.error_class == (
        FailureClass.INVALID_OUTPUT
    )
    coordinator.advance("steer-stale-result")
    assert ledger.get_run("steer-stale-result").state.status == RunStatus.FAILED


@pytest.mark.asyncio
async def test_restart_recovery_settles_known_terminal_and_retains_unknown_capacity(
    tmp_path, app_config, ledger_owner
) -> None:
    ledger, old_ownership = ledger_owner

    def known_terminal_script(spec):
        event = _worker_script(spec).events[0]
        return AttemptScript(
            events=(event,),
            reconciliations=(
                Reconciliation(
                    known=True,
                    status=AttemptStatus.SUCCEEDED,
                    terminal_result=event.result,
                ),
            ),
            event_barrier=True,
        )

    _create_run(ledger, app_config, "review", "recovery-known")
    original, backend, clock = _coordinator(
        ledger, old_ownership, factory=known_terminal_script, auto_release=False
    )
    original.advance("recovery-known")
    original.advance("recovery-known")
    await original.dispatch_pending("recovery-known")
    attempt = ledger.list_attempts("recovery-known")[0]
    await backend.wait_until_waiting(attempt.spec.attempt_id, 0)

    restarted = ExecutionCoordinator(ledger, backend, old_ownership, clock=clock)
    assert await restarted.recover("recovery-known") == 1
    assert ledger.get_attempt(attempt.spec.attempt_id).state.status == AttemptStatus.SUCCEEDED
    assert all(
        item.status.value == "released" for item in ledger.list_reservations("recovery-known")
    )
    await original.wait_for_workers()

    _create_run(ledger, app_config, "review", "recovery-unknown")

    def unknown_script(spec):
        return AttemptScript(
            events=_worker_script(spec).events,
            reconciliations=(Reconciliation(known=False, detail="no terminal evidence"),),
            event_barrier=True,
        )

    uncertain, unknown_backend, unknown_clock = _coordinator(
        ledger, old_ownership, factory=unknown_script, auto_release=False
    )
    uncertain.advance("recovery-unknown")
    uncertain.advance("recovery-unknown")
    await uncertain.dispatch_pending("recovery-unknown")
    unknown_attempt = ledger.list_attempts("recovery-unknown")[0]
    await unknown_backend.wait_until_waiting(unknown_attempt.spec.attempt_id, 0)
    restarted_unknown = ExecutionCoordinator(
        ledger, unknown_backend, old_ownership, clock=unknown_clock
    )
    await restarted_unknown.recover("recovery-unknown")
    assert ledger.get_attempt(unknown_attempt.spec.attempt_id).state.status == (
        AttemptStatus.OUTCOME_UNKNOWN
    )
    assert ledger.get_run("recovery-unknown").state.status == RunStatus.ATTENTION_REQUIRED
    assert any(item.status.value == "held" for item in ledger.list_reservations("recovery-unknown"))
    handle = uncertain._worker_handle(ledger.get_attempt(unknown_attempt.spec.attempt_id))
    assert handle is not None
    assert (await unknown_backend.close(handle)).settled
    await uncertain.wait_for_workers()


@pytest.mark.asyncio
async def test_allowed_redirect_is_persisted_and_used_for_the_next_handoff(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    _create_run(ledger, app_config, "prototype", "redirect-run")
    coordinator, _backend, _clock = _coordinator(ledger, ownership, factory=_worker_script)

    receipt = await coordinator.apply_intervention(
        RedirectIntervention(
            command_id=uuid4(),
            actor="user",
            target="implement",
            expected_run_revision=ledger.get_run("redirect-run").state.revision,
            kind=InterventionKind.REDIRECT,
            run_id="redirect-run",
            stage_id="implement",
            recipient_profile_id="implementer",
        )
    )
    assert receipt.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_stage_redirect("redirect-run", "implement") == "implementer"
    assert await coordinator.run_until_stalled("redirect-run") == RunStatus.SUCCEEDED
    implement = ledger.list_attempts("redirect-run", "implement")
    assert len(implement) == 1
    assert implement[0].spec.profile_id == "implementer"


@pytest.mark.asyncio
async def test_retry_after_known_selected_stop_creates_child_attempt(
    app_config, ledger_owner
) -> None:
    ledger, ownership = ledger_owner
    workflow = next(item for item in app_config.workflows if item.id == "review")
    profile_id = next(item.default_profile for item in workflow.stages if item.id == "review")
    agents = app_config.agents.model_copy(
        update={
            "agents": [
                agent.model_copy(
                    update={
                        "retry_policy": agent.retry_policy.model_copy(
                            update={
                                "max_attempts": 2,
                                "recoverable_classes": (FailureClass.CANCELLED,),
                            }
                        )
                    }
                )
                if agent.id == profile_id
                else agent
                for agent in app_config.agents.agents
            ]
        }
    )
    adjusted_config = replace(app_config, agents=agents)
    _create_run(ledger, adjusted_config, "review", "retry-run")
    coordinator, backend, _clock = _coordinator(
        ledger,
        ownership,
        factory=lambda spec: AttemptScript(
            events=_worker_script(spec).events,
            event_barrier=True,
        ),
        auto_release=False,
    )
    coordinator.advance("retry-run")
    coordinator.advance("retry-run")
    await coordinator.dispatch_pending("retry-run")
    prior = ledger.list_attempts("retry-run")[0]
    await backend.wait_until_waiting(prior.spec.attempt_id, 0)
    stopped = await coordinator.apply_intervention(
        StopAttemptIntervention(
            command_id=uuid4(),
            actor="user",
            target=prior.spec.attempt_id,
            expected_run_revision=ledger.get_run("retry-run").state.revision,
            kind=InterventionKind.STOP_ATTEMPT,
            run_id="retry-run",
            attempt_id=prior.spec.attempt_id,
        )
    )
    assert stopped.outcome == CommandOutcome.ACCEPTED
    assert ledger.get_attempt(prior.spec.attempt_id).state.safe_to_retry

    run = ledger.get_run("retry-run")
    retry = await coordinator.apply_intervention(
        RetryIntervention(
            command_id=uuid4(),
            actor="user",
            target=prior.spec.attempt_id,
            expected_run_revision=run.state.revision,
            kind=InterventionKind.RETRY,
            run_id="retry-run",
            attempt_id=prior.spec.attempt_id,
        )
    )
    assert retry.outcome == CommandOutcome.ACCEPTED
    attempts = ledger.list_attempts("retry-run", "review")
    assert len(attempts) == 2
    child = next(item for item in attempts if item.spec.attempt_id != prior.spec.attempt_id)
    assert child.spec.parent_attempt_id == prior.spec.attempt_id
    assert child.spec.attempt_id != prior.spec.attempt_id
    assert child.state.status == AttemptStatus.LAUNCHING
    await coordinator.wait_for_workers()
