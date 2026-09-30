import hashlib
import sqlite3
from datetime import UTC, datetime
from io import BytesIO
from uuid import uuid4

import pytest

from orchestrator.artifacts import ArtifactPathError, ArtifactStore
from orchestrator.domain.backend import ArtifactEntry, OutputStatus, WorkerResult
from orchestrator.domain.models import (
    AgentRunSpec,
    AttemptState,
    AttemptStatus,
    Effort,
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
)
from orchestrator.persistence.models import (
    ArtifactPublication,
    AttemptRegistration,
    AttemptResultRegistration,
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
        assert ledger.schema_version == 3

    with SQLiteLedger(path) as reopened:
        assert reopened.schema_version == 3


def test_database_rejects_a_schema_newer_than_this_application(tmp_path) -> None:
    path = tmp_path / "orchestrator.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA user_version = 999")

    with pytest.raises(UnsupportedSchemaVersion, match="999"):
        SQLiteLedger(path)


def test_v1_database_receives_additive_result_and_control_migrations(tmp_path) -> None:
    from orchestrator.persistence.migrations import MIGRATIONS

    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        MIGRATIONS[0][2](connection)
        connection.execute(
            "INSERT INTO schema_migrations(version, name, applied_at) VALUES (1, ?, ?)",
            (MIGRATIONS[0][1], STAMP.isoformat()),
        )
        connection.execute("PRAGMA user_version = 1")

    with SQLiteLedger(path) as ledger:
        assert ledger.schema_version == 3
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(stages)").fetchall()}
        assert "result_payload" in columns
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'attempt_results'"
            ).fetchone()
            is not None
        )
        assert {
            "attention_reason",
            "resume_status",
        } <= {row[1] for row in connection.execute("PRAGMA table_info(runs)").fetchall()}
        assert {
            "intervention_records",
            "stage_redirects",
        } <= {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }


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
