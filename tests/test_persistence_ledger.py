import hashlib
import sqlite3
from datetime import UTC, datetime
from io import BytesIO
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from orchestrator.artifacts import ArtifactPathError, ArtifactStore
from orchestrator.backends.codex_output import retain_read_only_report
from orchestrator.domain.backend import (
    ArtifactEntry,
    BackendPreflightSnapshot,
    OutputStatus,
    PreflightFact,
    WorkerResult,
)
from orchestrator.domain.decisions import (
    DecisionAcceptancePolicy,
    DecisionDispositionStatus,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    decision_request_hash,
    evaluate_decision,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    AttemptState,
    AttemptStatus,
    BackendPreflightRecordedEvent,
    Effort,
    EventKind,
    Handoff,
    InterventionRequestedEvent,
    ModelBindingSettings,
    PauseIntervention,
    PermissionSet,
    RunStatus,
    RunStatusChangedEvent,
    SandboxMode,
)
from orchestrator.persistence import SQLiteLedger, UnsupportedSchemaVersion
from orchestrator.persistence.ledger import (
    CommandIdConflict,
    ImmutableSpecificationConflict,
    LedgerInvariantError,
    ReservationConflict,
    canonical_json,
    content_hash,
)
from orchestrator.persistence.models import (
    ArtifactPublication,
    AttemptRegistration,
    AttemptResultRegistration,
    BackendPreflightRecord,
    DecisionRecord,
    LedgerMutation,
    OutboxIntent,
    OutboxStatus,
    ReservationChange,
    ReservationOperation,
    RunProjectionUpdate,
    StageResult,
    StageUpdate,
)
from orchestrator.persistence.ownership import CoordinatorOwnership, OwnershipUnavailable
from orchestrator.resolution import resolve_run

STAMP = datetime(2026, 9, 29, tzinfo=UTC)


def _run_inputs(app_config):
    project = app_config.project.model_copy(
        update={
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex", model_id="offline-model", allowed_efforts=["high"]
                )
            }
        }
    )
    workflow = next(item for item in app_config.workflows if item.id == "review")
    spec = resolve_run(
        "Review the current changes",
        project,
        workflow,
        app_config.agents.agents,
        model_availability={"codex": {"offline-model": {Effort.HIGH}}},
    )
    return project, spec


def _create_run(ledger, app_config, run_id="run-1"):
    project, spec = _run_inputs(app_config)
    ledger.create_run(run_id, project, spec, uuid4(), actor="test", occurred_at=STAMP)
    return project, spec


def _attempt_spec(run_id, run_snapshot_hash, attempt_id="attempt-1"):
    return AgentRunSpec(
        run_id=run_id,
        attempt_id=attempt_id,
        profile_id="reviewer",
        profile_version="1.0.0",
        instructions="Review the current patch",
        input_manifest=(),
        backend="fake",
        model_id="fake-model",
        effort="high",
        permissions=PermissionSet(sandbox=SandboxMode.READ_ONLY),
        skills=(),
        tools=("read_files",),
        run_snapshot_hash=run_snapshot_hash,
    )


def test_database_is_versioned_and_survives_reopen(tmp_path) -> None:
    path = tmp_path / "orchestrator.sqlite3"

    with SQLiteLedger(path) as ledger:
        assert ledger.schema_version == 5

    with SQLiteLedger(path) as reopened:
        assert reopened.schema_version == 5


def test_database_rejects_a_schema_newer_than_this_application(tmp_path) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(UnsupportedSchemaVersion, match="999"):
        SQLiteLedger(path)


@pytest.mark.parametrize("old_version", [1, 2, 3, 4])
def test_old_database_migrates_without_rewriting_snapshots(
    tmp_path, app_config, old_version
) -> None:
    from orchestrator.persistence.migrations import MIGRATIONS

    path = tmp_path / "legacy.sqlite3"
    project, spec = _run_inputs(app_config)
    legacy = spec.model_dump(mode="json", exclude={"snapshot_hash"})
    legacy["workflow"]["policy"].pop("decision_questions")
    legacy_hash = content_hash(canonical_json(legacy))
    legacy["snapshot_hash"] = legacy_hash
    legacy_payload = canonical_json(legacy)
    with sqlite3.connect(path) as connection:
        for version, name, migration in MIGRATIONS[:old_version]:
            migration(connection)
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, STAMP.isoformat()),
            )
        connection.execute(f"PRAGMA user_version = {old_version}")
        connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)",
            (
                project.id,
                project.name,
                project.path,
                project.settings_revision,
                STAMP.isoformat(),
                STAMP.isoformat(),
            ),
        )
        payload = canonical_json(project)
        connection.execute(
            "INSERT INTO project_configs VALUES (?, ?, 1, ?, ?, ?)",
            (
                project.id,
                project.settings_revision,
                payload,
                content_hash(payload),
                STAMP.isoformat(),
            ),
        )
        connection.execute(
            "INSERT INTO run_specs VALUES (?, 1, ?, ?)",
            (legacy_hash, legacy_payload, STAMP.isoformat()),
        )
        connection.execute(
            "INSERT INTO runs(run_id, project_id, settings_revision, snapshot_hash, status, "
            "revision, active_stages, attempts_used, elapsed_seconds, created_at, updated_at) "
            "VALUES ('legacy', ?, ?, ?, 'ready', 0, '[]', 0, 0, ?, ?)",
            (
                project.id,
                project.settings_revision,
                legacy_hash,
                STAMP.isoformat(),
                STAMP.isoformat(),
            ),
        )
        for stage in spec.workflow.stages:
            connection.execute(
                "INSERT INTO stages(run_id, stage_id, definition, status, updated_at) "
                "VALUES ('legacy', ?, ?, 'pending', ?)",
                (stage.id, canonical_json(stage), STAMP.isoformat()),
            )

    with SQLiteLedger(path) as ledger:
        assert ledger.schema_version == 5
        restored = ledger.get_run("legacy")
        assert restored.spec.snapshot_hash == legacy_hash
        assert restored.spec.workflow.policy.decision_questions == ()
        assert restored.spec.task == spec.task
        assert ledger.list_decision_records("legacy") == ()
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT payload FROM run_specs").fetchone()[0] == legacy_payload
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        columns = {row[1] for row in connection.execute("PRAGMA table_info(stages)").fetchall()}
        assert "result_payload" in columns
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'attempt_results'"
            ).fetchone()
            is not None
        )
        assert {"attention_reason", "resume_status"} <= {
            row[1] for row in connection.execute("PRAGMA table_info(runs)").fetchall()
        }
        assert {
            "intervention_records",
            "stage_redirects",
            "decision_records",
        } <= {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


def test_backend_preflight_record_and_event_are_immutable_and_survive_reopen(
    tmp_path, app_config
) -> None:
    path = tmp_path / "preflight.sqlite3"
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        spec = _attempt_spec("run-1", run_spec.snapshot_hash)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="test",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=spec,
                        stage_id="review",
                        slot_id="review/slot-01",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.LAUNCHING),
                    ),
                ),
            )
        )
        snapshot = BackendPreflightSnapshot(
            preparation_id="prep-1",
            observed_at=STAMP,
            runtime=(PreflightFact(key="runtime_version", value="0.159.2", state="verified"),),
        )
        record_data = {
            "record_id": "preflight-1",
            "run_id": "run-1",
            "attempt_id": "attempt-1",
            "preparation_id": "prep-1",
            "attempt_spec_hash": content_hash(canonical_json(spec)),
            "accepted": True,
            "occurred_at": STAMP,
            "snapshot": snapshot,
        }
        record = BackendPreflightRecord(**record_data, record_hash="0" * 64)
        record_hash = content_hash(
            canonical_json(record.model_dump(mode="json", exclude={"record_hash"}))
        )
        record = record.model_copy(update={"record_hash": record_hash})
        event = BackendPreflightRecordedEvent(
            event_id=uuid4(),
            run_id="run-1",
            occurred_at=STAMP,
            actor="test",
            kind=EventKind.BACKEND_PREFLIGHT_RECORDED,
            record_id=record.record_id,
            attempt_id=record.attempt_id,
            preparation_id=record.preparation_id,
            record_hash=record.record_hash,
            accepted=True,
        )
        current = ledger.get_attempt("attempt-1")
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=1,
                actor="test",
                occurred_at=STAMP,
                attempt_updates=(
                    current.state.model_copy(
                        update={
                            "backend_preflight_record_id": record.record_id,
                            "backend_preflight_record_hash": record.record_hash,
                        }
                    ),
                ),
                backend_preflight_records=(record,),
                events=(event,),
            )
        )
        assert ledger.get_backend_preflight_record(record.record_id) == record
        assert ledger.list_backend_preflight_records("run-1") == (record,)
        assert ledger.get_attempt("attempt-1").state.backend_preflight_record_hash == record_hash
        assert any(
            item.kind == EventKind.BACKEND_PREFLIGHT_RECORDED
            for item in ledger.list_events("run-1")
        )

    with SQLiteLedger(path) as reopened:
        assert reopened.get_backend_preflight_record("preflight-1") == record
        assert reopened.list_backend_preflight_records("run-1") == (record,)
        current = reopened.get_attempt("attempt-1")
        with pytest.raises(LedgerInvariantError, match="link is immutable"):
            reopened.apply(
                LedgerMutation(
                    command_id=uuid4(),
                    run_id="run-1",
                    expected_revision=2,
                    actor="test",
                    occurred_at=STAMP,
                    attempt_updates=(
                        current.state.model_copy(
                            update={
                                "backend_preflight_record_id": "another-record",
                                "backend_preflight_record_hash": "1" * 64,
                            }
                        ),
                    ),
                )
            )
        with sqlite3.connect(path) as connection:
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                connection.execute(
                    "DELETE FROM backend_preflight_records WHERE record_id = ?",
                    (record.record_id,),
                )


def test_codex_read_only_report_is_bounded_and_retained_from_exact_bytes(
    tmp_path, app_config, repo_root
) -> None:
    with SQLiteLedger(tmp_path / "codex-output.sqlite3") as ledger:
        _, run_spec = _create_run(ledger, app_config)
        spec = _attempt_spec("run-1", run_spec.snapshot_hash)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="test",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=spec,
                        stage_id="review",
                        slot_id="review/slot-01",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.RUNNING),
                    ),
                ),
            )
        )
        raw = (repo_root / "tests/fixtures/backends/codex-read-only-result-v1.json").read_bytes()
        store = ArtifactStore(tmp_path / "artifacts", ledger)
        result = retain_read_only_report(raw, spec, ledger, store, observed_at=STAMP)
        artifact_id = str(
            uuid5(
                NAMESPACE_URL,
                f"codex-report:{spec.attempt_id}:{content_hash(raw)}",
            )
        )

        assert result.status == OutputStatus.PASS
        assert len(result.artifacts) == 1
        assert result.artifacts[0].name == "report"
        assert result.artifacts[0].schema_id == "codex-read-only-result-v1"
        assert result.artifacts[0].content_hash == content_hash(raw)
        assert store.read(artifact_id) == raw
        malformed = b"{}"
        malformed_id = str(
            uuid5(
                NAMESPACE_URL,
                f"codex-report:{spec.attempt_id}:{content_hash(malformed)}",
            )
        )
        with pytest.raises(ValueError, match="does not match"):
            retain_read_only_report(malformed, spec, ledger, store, observed_at=STAMP)
        assert store.read(malformed_id) == malformed
        oversized_prefix = b" " * 65_536
        oversized_id = str(
            uuid5(
                NAMESPACE_URL,
                f"codex-report:{spec.attempt_id}:{content_hash(oversized_prefix)}",
            )
        )
        with pytest.raises(ValueError, match="byte limit"):
            retain_read_only_report(b" " * 65_537, spec, ledger, store, observed_at=STAMP)
        assert store.read(oversized_id) == oversized_prefix


@pytest.mark.parametrize(
    "fixture_name",
    [
        "deterministic-policy",
        "native-decision-model",
        "general-llm-readout",
        "generative-structured-output",
    ],
)
def test_decision_request_and_disposition_survive_reopen_write_once(
    tmp_path,
    app_config,
    repo_root,
    fixture_name,
) -> None:
    fixture = DecisionResult.model_validate_json(
        (repo_root / "tests" / "fixtures" / "decisions" / f"{fixture_name}.json").read_text()
    )
    path = tmp_path / "decisions.sqlite3"
    with SQLiteLedger(path) as ledger:
        _create_run(ledger, app_config)
        request = DecisionRequest(
            decision_id=uuid4(),
            run_id="run-1",
            current_run_revision=0,
            question_id="implementer_choice",
            question_revision="1",
            question="Choose an approved specialist.",
            allowed_outcomes=(
                DecisionOption(outcome_id="prototype-implementer", label="Prototype implementer"),
                DecisionOption(outcome_id="implementer", label="Implementer"),
            ),
            inference_binding=fixture.effective_inference,
            acceptance_policy=DecisionAcceptancePolicy(
                policy_id="typed_outcome",
                revision="1",
                mode="typed_outcome",
                understood_score_semantics=("probability_distribution_v1",),
                required_calibration=fixture.effective_inference.calibration,
            ),
            created_at=STAMP,
        )
        pending = DecisionRecord(
            request=request,
            request_hash=decision_request_hash(request),
            request_persisted_revision=1,
            created_at=STAMP,
        )
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                run_update=RunProjectionUpdate(),
                decision_records=(pending,),
            )
        )
        result = fixture.model_copy(
            update={
                "decision_id": request.decision_id,
                "consumed_run_revision": request.current_run_revision,
                "consumed_evidence_digest": request.evidence_digest,
            }
        )
        disposition = evaluate_decision(
            request,
            result,
            current_run_revision=0,
            currently_allowed_outcomes={"prototype-implementer", "implementer"},
            evaluated_at=STAMP,
        ).model_copy(update={"resulting_run_revision": 2})
        assert disposition.status == DecisionDispositionStatus.ACCEPTED
        completed = pending.model_copy(
            update={"result": result, "disposition": disposition, "completed_at": STAMP}
        )
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=1,
                actor="coordinator",
                occurred_at=STAMP,
                run_update=RunProjectionUpdate(),
                decision_records=(completed,),
            )
        )

    with SQLiteLedger(path) as reopened:
        record = reopened.get_decision_record(request.decision_id)
        assert record.result == result
        assert record.disposition == disposition
        assert reopened.list_decision_records("run-1") == (record,)
        changed = record.model_copy(
            update={"disposition": disposition.model_copy(update={"policy_revision": "2"})}
        )
        with pytest.raises(LedgerInvariantError, match="write-once"):
            reopened.apply(
                LedgerMutation(
                    command_id=uuid4(),
                    run_id="run-1",
                    expected_revision=2,
                    actor="coordinator",
                    occurred_at=STAMP,
                    run_update=RunProjectionUpdate(),
                    decision_records=(changed,),
                )
            )


def test_normalized_attempt_results_and_stage_outputs_survive_reopen_immutably(
    tmp_path, app_config
) -> None:
    path = tmp_path / "results.sqlite3"
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        output = ArtifactEntry(
            name="report",
            schema_id="review-report-v1",
            content_hash="a" * 64,
        )
        worker_result = WorkerResult(
            attempt_id="attempt-1",
            input_revision="b" * 64,
            status=OutputStatus.FAIL,
            summary="valid report with findings",
            artifacts=(output,),
        )
        stage_result = StageResult(
            outputs=(output,),
            result_status=OutputStatus.FAIL,
        )
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=_attempt_spec("run-1", run_spec.snapshot_hash),
                        stage_id="review",
                        slot_id="review/slot-01",
                        state=AttemptState(
                            attempt_id="attempt-1",
                            status=AttemptStatus.SUCCEEDED,
                            started_at=STAMP,
                            finished_at=STAMP,
                        ),
                    ),
                ),
                attempt_results=(
                    AttemptResultRegistration(attempt_id="attempt-1", result=worker_result),
                ),
                stage_updates=(
                    StageUpdate(
                        stage_id="review",
                        status="succeeded",
                        result=stage_result,
                    ),
                ),
            )
        )
        first_attempt = ledger.get_attempt("attempt-1")
        assert first_attempt.result is not None
        assert first_attempt.result.result == worker_result
        assert ledger.get_run("run-1").stages[0].result == stage_result
        assert any(event.kind == "attempt_result_recorded" for event in ledger.list_events("run-1"))

    with SQLiteLedger(path) as reopened:
        assert reopened.get_attempt("attempt-1").result.result == worker_result
        assert reopened.get_run("run-1").stages[0].result == stage_result
        altered = worker_result.model_copy(update={"summary": "changed immutable evidence"})
        with pytest.raises(ImmutableSpecificationConflict, match="another terminal result"):
            reopened.apply(
                LedgerMutation(
                    command_id=uuid4(),
                    run_id="run-1",
                    expected_revision=1,
                    actor="test",
                    occurred_at=STAMP,
                    attempt_results=(
                        AttemptResultRegistration(attempt_id="attempt-1", result=altered),
                    ),
                )
            )


def test_immutable_run_and_project_snapshots_survive_reopen(tmp_path, app_config) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    project, run_spec = _run_inputs(app_config)
    command_id = uuid4()
    created_at = STAMP

    with SQLiteLedger(path) as ledger:
        receipt = ledger.create_run(
            "run-1", project, run_spec, command_id, actor="test", occurred_at=created_at
        )
        assert receipt.outcome == "accepted"

    changed_project = project.model_copy(update={"name": "Changed name", "settings_revision": "2"})
    with SQLiteLedger(path) as ledger:
        ledger.save_project_config(changed_project)
        duplicate = ledger.create_run(
            "run-1",
            project,
            run_spec,
            uuid4(),
            actor="test",
            occurred_at=created_at,
        )
        run = ledger.get_run("run-1")
        events = ledger.list_events("run-1")

    assert duplicate.outcome == "accepted"
    assert duplicate.event_sequences == ()
    assert run.project_config.name == project.name
    assert run.project_config.settings_revision == project.settings_revision
    assert run.spec == run_spec
    assert run.state.revision == 0
    assert run.state.status.value == "ready"
    assert [event.sequence for event in events] == [1]


def test_revision_command_is_applied_once_and_stale_receipt_survives_reopen(
    tmp_path, app_config
) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with SQLiteLedger(path) as ledger:
        _create_run(ledger, app_config)
        command_id = uuid4()
        mutation = LedgerMutation(
            command_id=command_id,
            run_id="run-1",
            expected_revision=0,
            actor="test",
            occurred_at=STAMP,
            run_update=RunProjectionUpdate(status=RunStatus.RUNNING),
        )
        accepted = ledger.apply(mutation)
        repeated = ledger.apply(mutation)

        stale_id = uuid4()
        stale = ledger.apply(
            LedgerMutation(
                command_id=stale_id,
                run_id="run-1",
                expected_revision=0,
                actor="test",
                occurred_at=STAMP,
                run_update=RunProjectionUpdate(status=RunStatus.FAILED),
            )
        )
        assert accepted == repeated
        assert accepted.outcome == "accepted"
        assert accepted.resulting_revision == 1
        assert accepted.event_sequences == (2,)
        assert stale.outcome == "rejected"
        assert stale.reason == "stale_revision: expected 0, current 1"
        assert len(ledger.list_events("run-1")) == 2

    with SQLiteLedger(path) as reopened:
        assert reopened.get_command_receipt(command_id) == accepted
        assert reopened.get_command_receipt(stale_id) == stale
        run = reopened.get_run("run-1")
        assert (run.state.status, run.state.revision) == (RunStatus.RUNNING, 1)

    with SQLiteLedger(path) as ledger:
        with pytest.raises(CommandIdConflict):
            ledger.apply(
                LedgerMutation(
                    command_id=command_id,
                    run_id="run-1",
                    expected_revision=0,
                    actor="test",
                    occurred_at=STAMP,
                    run_update=RunProjectionUpdate(status=RunStatus.FAILED),
                )
            )


def test_failed_mutation_rolls_back_projection_event_outbox_and_reservation(
    tmp_path, app_config
) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    action_id = uuid4()
    event = RunStatusChangedEvent(
        event_id=uuid4(),
        run_id="run-1",
        occurred_at=STAMP,
        actor="test",
        kind="run_status_changed",
        previous=RunStatus.READY,
        current=RunStatus.RUNNING,
    )
    with SQLiteLedger(path) as ledger:
        _create_run(ledger, app_config)
        mutation = LedgerMutation(
            command_id=uuid4(),
            run_id="run-1",
            expected_revision=0,
            actor="test",
            occurred_at=STAMP,
            run_update=RunProjectionUpdate(status=RunStatus.RUNNING),
            stage_updates=(StageUpdate(stage_id="missing-stage", status="running"),),
            events=(event,),
            outbox_actions=(
                OutboxIntent(
                    action_id=action_id,
                    action_key="launch-run-1",
                    kind="launch_attempt",
                    payload={"attempt_id": "attempt-1"},
                ),
            ),
            reservations=(
                ReservationChange(
                    operation=ReservationOperation.RESERVE,
                    reservation_id="reservation-1",
                    reservation_key="attempt-1:slot",
                    scope="run",
                    resource_key="run-1",
                ),
            ),
        )
        with pytest.raises(LedgerInvariantError, match="missing stage"):
            ledger.apply(mutation)

        run = ledger.get_run("run-1")
        assert (run.state.status, run.state.revision) == (RunStatus.READY, 0)
        assert [event.sequence for event in ledger.list_events("run-1")] == [1]
        assert ledger.list_outbox_actions("run-1") == ()
        assert ledger.list_reservations("run-1") == ()
        assert ledger.get_command_receipt(mutation.command_id) is None


def test_attempt_outbox_and_reservation_recover_without_relaunching_claimed_action(
    tmp_path, app_config
) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    action_id = uuid4()
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        attempt_spec = _attempt_spec("run-1", run_spec.snapshot_hash)
        mutation = LedgerMutation(
            command_id=uuid4(),
            run_id="run-1",
            expected_revision=0,
            actor="coordinator",
            occurred_at=STAMP,
            run_update=RunProjectionUpdate(attempts_used=1),
            attempt_creations=(
                AttemptRegistration(
                    spec=attempt_spec,
                    stage_id="review",
                    slot_id="review/1",
                    state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                ),
            ),
            outbox_actions=(
                OutboxIntent(
                    action_id=action_id,
                    action_key="launch:attempt-1",
                    kind="launch_attempt",
                    payload={"attempt_id": "attempt-1"},
                ),
            ),
            reservations=(
                ReservationChange(
                    operation=ReservationOperation.RESERVE,
                    reservation_id="reservation-1",
                    reservation_key="attempt-1:run-slot",
                    attempt_id="attempt-1",
                    scope="run",
                    resource_key="run-1",
                ),
            ),
        )
        receipt = ledger.apply(mutation)
        assert receipt.resulting_revision == 1
        assert receipt.event_sequences == (2, 3, 4)
        assert ledger.get_attempt("attempt-1").spec == attempt_spec
        assert ledger.list_outbox_actions("run-1")[0].status == OutboxStatus.PENDING
        assert ledger.list_reservations("run-1")[0].status.value == "held"

        claimed = ledger.claim_next_outbox("dispatcher-1", STAMP)
        assert claimed is not None
        assert claimed.action_id == action_id
        assert claimed.status == OutboxStatus.CLAIMED
        assert claimed.claimed_by == "dispatcher-1"

    with SQLiteLedger(path) as reopened:
        assert reopened.get_attempt("attempt-1").state.status == AttemptStatus.PENDING
        assert reopened.get_outbox_action(action_id).status == OutboxStatus.CLAIMED
        assert reopened.get_run("run-1").state.revision == 2
        assert [event.sequence for event in reopened.list_events("run-1")] == [1, 2, 3, 4, 5]
        assert reopened.claim_next_outbox("dispatcher-2", STAMP) is None

        ack_id = uuid4()
        acknowledged = reopened.record_outbox_outcome(
            action_id,
            ack_id,
            expected_revision=2,
            status=OutboxStatus.ACKNOWLEDGED,
            result="started",
            actor="dispatcher-1",
            occurred_at=STAMP,
        )
        duplicate_ack = reopened.record_outbox_outcome(
            action_id,
            ack_id,
            expected_revision=2,
            status=OutboxStatus.ACKNOWLEDGED,
            result="started",
            actor="dispatcher-1",
            occurred_at=STAMP.replace(minute=1),
        )
        assert acknowledged == duplicate_ack
        assert acknowledged.resulting_revision == 3
        assert reopened.get_outbox_action(action_id).result == "started"
        assert reopened.get_run("run-1").state.revision == 3
        assert [event.sequence for event in reopened.list_events("run-1")] == [1, 2, 3, 4, 5, 6]
        repeated_outcome = reopened.record_outbox_outcome(
            action_id,
            uuid4(),
            expected_revision=3,
            status=OutboxStatus.ACKNOWLEDGED,
            result="started",
            actor="dispatcher-1",
            occurred_at=STAMP,
        )
        assert repeated_outcome.resulting_revision == 3
        assert [event.sequence for event in reopened.list_events("run-1")] == [1, 2, 3, 4, 5, 6]


def test_attempt_stage_foreign_key_rejects_invalid_registration(tmp_path, app_config) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        invalid = LedgerMutation(
            command_id=uuid4(),
            run_id="run-1",
            expected_revision=0,
            actor="coordinator",
            occurred_at=STAMP,
            attempt_creations=(
                AttemptRegistration(
                    spec=_attempt_spec("run-1", run_spec.snapshot_hash),
                    stage_id="missing-stage",
                    slot_id="review/1",
                    state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                ),
            ),
        )
        with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"):
            ledger.apply(invalid)
        assert ledger.get_run("run-1").state.revision == 0
        assert [event.sequence for event in ledger.list_events("run-1")] == [1]


def test_artifact_publication_is_content_addressed_and_survives_reopen(
    tmp_path, app_config
) -> None:
    database = tmp_path / "orchestrator.sqlite3"
    data_dir = tmp_path / "data"
    content = b"review evidence\n" * 4_000
    with SQLiteLedger(database) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        attempt_spec = _attempt_spec("run-1", run_spec.snapshot_hash)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=attempt_spec,
                        stage_id="review",
                        slot_id="review/1",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                    ),
                ),
            )
        )
        publication = ArtifactPublication(
            command_id=uuid4(),
            expected_run_revision=1,
            actor="worker:attempt-1",
            run_id="run-1",
            attempt_id="attempt-1",
            artifact_id="artifact-1",
            input_revision="inputs-v1",
            schema_id="review-report-v1",
            occurred_at=STAMP,
        )
        store = ArtifactStore(data_dir, ledger)
        manifest = store.publish(publication, BytesIO(content))

        assert manifest.size_bytes == len(content)
        assert manifest.artifact.content_hash == hashlib.sha256(content).hexdigest()
        assert manifest.artifact.relative_path.startswith("runs/run-1/attempts/attempt-1/")
        assert store.read("artifact-1") == content
        assert [event.sequence for event in ledger.list_events("run-1")] == [1, 2, 3]
        assert ledger.get_run("run-1").state.revision == 2

    with SQLiteLedger(database) as reopened:
        manifest = reopened.get_artifact_manifest("artifact-1")
        assert manifest is not None
        assert ArtifactStore(data_dir, reopened).read("artifact-1") == content


def test_failed_artifact_write_leaves_no_file_or_manifest_and_rejects_traversal(
    tmp_path, app_config
) -> None:
    class InterruptedStream:
        reads = 0

        def read(self, size):
            self.reads += 1
            if self.reads == 1:
                return b"partial artifact"
            raise OSError("simulated interrupted write")

    database = tmp_path / "orchestrator.sqlite3"
    data_dir = tmp_path / "data"
    with SQLiteLedger(database) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=_attempt_spec("run-1", run_spec.snapshot_hash),
                        stage_id="review",
                        slot_id="review/1",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                    ),
                ),
            )
        )
        store = ArtifactStore(data_dir, ledger)
        publication = ArtifactPublication(
            command_id=uuid4(),
            expected_run_revision=1,
            actor="worker:attempt-1",
            run_id="run-1",
            attempt_id="attempt-1",
            artifact_id="broken-artifact",
            input_revision="inputs-v1",
            schema_id="review-report-v1",
            occurred_at=STAMP,
        )

        with pytest.raises(OSError, match="simulated interrupted write"):
            store.publish(publication, InterruptedStream())

        assert ledger.get_artifact_manifest("broken-artifact") is None
        assert list(data_dir.rglob(".partial-*")) == []
        assert list(data_dir.rglob("artifacts/*")) == []
        with pytest.raises(ArtifactPathError, match="run ID"):
            store.publish(
                publication.model_copy(update={"run_id": "../outside"}),
                BytesIO(b"unsafe"),
            )


def test_owner_lock_is_exclusive_and_generation_increments_after_reacquisition(tmp_path) -> None:
    database = tmp_path / "orchestrator.sqlite3"
    lock_path = tmp_path / "coordinator.lock"
    with SQLiteLedger(database) as first_ledger, SQLiteLedger(database) as second_ledger:
        first = CoordinatorOwnership(first_ledger, lock_path)
        second = CoordinatorOwnership(second_ledger, lock_path)
        first_lease = first.acquire("owner-one", STAMP)
        assert first_lease.generation == 1
        assert first_lease.owner_id == "owner-one"

        with pytest.raises(OwnershipUnavailable, match="lock is held"):
            second.acquire("owner-two", STAMP)

        first.release(STAMP.replace(minute=1))
        second_lease = second.acquire("owner-two", STAMP.replace(minute=2))
        assert second_lease.generation == 2
        assert second_lease.owner_id == "owner-two"
        second.release(STAMP.replace(minute=3))


def test_reservation_cannot_be_released_until_attempt_is_settled(tmp_path, app_config) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=_attempt_spec("run-1", run_spec.snapshot_hash),
                        stage_id="review",
                        slot_id="review/1",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                    ),
                ),
                reservations=(
                    ReservationChange(
                        operation=ReservationOperation.RESERVE,
                        reservation_id="reservation-1",
                        reservation_key="attempt-1:worker-slot",
                        attempt_id="attempt-1",
                        scope="run",
                        resource_key="run-1",
                    ),
                ),
            )
        )
        release = ReservationChange(
            operation=ReservationOperation.RELEASE,
            reservation_id="reservation-1",
            reservation_key="attempt-1:worker-slot",
        )
        with pytest.raises(ReservationConflict, match="only after settlement"):
            ledger.apply(
                LedgerMutation(
                    command_id=uuid4(),
                    run_id="run-1",
                    expected_revision=1,
                    actor="coordinator",
                    occurred_at=STAMP,
                    reservations=(release,),
                )
            )
        assert ledger.list_reservations("run-1")[0].status.value == "held"

        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=1,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_updates=(
                    AttemptState(
                        attempt_id="attempt-1",
                        status=AttemptStatus.SUCCEEDED,
                        finished_at=STAMP,
                    ),
                ),
                reservations=(release,),
            )
        )
        assert ledger.list_reservations("run-1")[0].status.value == "released"


def test_interventions_and_handoffs_are_retrievable_after_reopen(tmp_path, app_config) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with SQLiteLedger(path) as ledger:
        _, run_spec = _create_run(ledger, app_config)
        ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id="run-1",
                expected_revision=0,
                actor="coordinator",
                occurred_at=STAMP,
                attempt_creations=(
                    AttemptRegistration(
                        spec=_attempt_spec("run-1", run_spec.snapshot_hash),
                        stage_id="review",
                        slot_id="review/1",
                        state=AttemptState(attempt_id="attempt-1", status=AttemptStatus.PENDING),
                    ),
                ),
            )
        )
        manifest = ArtifactStore(tmp_path / "data", ledger).publish(
            ArtifactPublication(
                command_id=uuid4(),
                expected_run_revision=1,
                actor="worker:attempt-1",
                run_id="run-1",
                attempt_id="attempt-1",
                artifact_id="handoff-artifact",
                input_revision="inputs-v1",
                schema_id="review-report-v1",
                occurred_at=STAMP,
            ),
            BytesIO(b"review report"),
        )
        intervention = PauseIntervention(
            command_id=uuid4(),
            actor="operator",
            target="run-1",
            expected_run_revision=2,
            kind="pause",
        )
        handoff = Handoff(
            source_attempt_id="attempt-1",
            destination_stage="handoff",
            destination_slot="handoff/1",
            input_revision="inputs-v1",
            content_hash=manifest.artifact.content_hash,
            project_revision="commit-123",
            schema_id="review-report-v1",
            relative_path=manifest.artifact.relative_path,
        )
        ledger.apply(
            LedgerMutation(
                command_id=intervention.command_id,
                run_id="run-1",
                expected_revision=2,
                actor="operator",
                occurred_at=STAMP,
                events=(
                    InterventionRequestedEvent(
                        event_id=uuid4(),
                        run_id="run-1",
                        occurred_at=STAMP,
                        actor="operator",
                        kind="intervention_requested",
                        intervention=intervention,
                    ),
                ),
                handoffs=(handoff,),
            )
        )

    with SQLiteLedger(path) as reopened:
        assert reopened.list_interventions("run-1") == (intervention,)
        assert reopened.list_handoffs("run-1") == (handoff,)
