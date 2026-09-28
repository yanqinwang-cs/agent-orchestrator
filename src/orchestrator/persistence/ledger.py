"""Transactional SQLite ledger for immutable run facts and mutable projections."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import RLock
from types import TracebackType
from typing import Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, TypeAdapter
from pydantic_core import to_jsonable_python

from orchestrator.domain.models import (
    AgentRunSpec,
    Artifact,
    ArtifactRecordedEvent,
    AttemptState,
    AttemptStatus,
    AttemptStatusChangedEvent,
    Event,
    EventKind,
    Handoff,
    HandoffRecordedEvent,
    Intervention,
    InterventionRequestedEvent,
    OutboxStatus,
    OutboxStatusChangedEvent,
    ProjectConfig,
    ReservationStatus,
    ReservationStatusChangedEvent,
    RunSpec,
    RunState,
    RunStatus,
    RunStatusChangedEvent,
    StageStatus,
    StageStatusChangedEvent,
)
from orchestrator.persistence.migrations import apply_migrations
from orchestrator.persistence.models import (
    ArtifactManifest,
    ArtifactPublication,
    ArtifactRegistration,
    AttemptRegistration,
    CommandOutcome,
    CommandReceipt,
    LedgerMutation,
    OutboxAction,
    OutboxIntent,
    OutboxOutcomeChange,
    OwnerLease,
    PersistedAttempt,
    PersistedRun,
    ReservationChange,
    ReservationOperation,
    ReservationRecord,
    StageProjection,
)

EVENT_ADAPTER: TypeAdapter[Event] = TypeAdapter(Event)


class UnsupportedSchemaVersion(RuntimeError):
    """Raised when a database was created by a newer application version."""


class LedgerError(RuntimeError):
    """Base class for invalid or conflicting ledger operations."""


class RunNotFound(LedgerError):
    """The requested run does not exist in this ledger."""


class CommandIdConflict(LedgerError):
    """A command UUID was reused for a different request."""


class ImmutableSpecificationConflict(LedgerError):
    """An immutable configuration or specification changed under an existing identity."""


class LedgerInvariantError(LedgerError):
    """A mutation violates a persisted runtime invariant."""


class ReservationConflict(LedgerError):
    """A reservation identity or ownership transition conflicts with existing state."""


class OutboxTransitionError(LedgerError):
    """An outbox action cannot make the requested delivery transition."""


def canonical_json(value: Any, *, exclude: set[str] | None = None) -> str:
    """Serialize JSON-compatible values with the run resolver's canonical rules."""

    if isinstance(value, BaseModel):
        data = value.model_dump(mode="json", exclude=exclude or set(), exclude_none=False)
    else:
        data = to_jsonable_python(value)
    return json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def content_hash(payload: str | bytes) -> str:
    """Return the stable SHA-256 digest for serialized content."""

    encoded = payload.encode("utf-8") if isinstance(payload, str) else payload
    return hashlib.sha256(encoded).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _json_model(model_type: type[BaseModel], payload: str) -> Any:
    return model_type.model_validate(json.loads(payload))


class SQLiteLedger:
    """Own the local SQLite connection and coordinate atomic run mutations."""

    def __init__(self, path: Path | str, busy_timeout_ms: int = 5_000) -> None:
        if busy_timeout_ms < 0:
            raise ValueError("busy_timeout_ms must not be negative")
        self.path = str(path)
        if self.path != ":memory:":
            expanded_path = Path(self.path).expanduser()
            expanded_path.parent.mkdir(parents=True, exist_ok=True)
            self.path = str(expanded_path)
        self._connection = sqlite3.connect(
            self.path,
            timeout=busy_timeout_ms / 1_000,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._mutex = RLock()
        self._closed = False
        try:
            apply_migrations(self._connection)
        except ValueError as error:
            self._connection.close()
            if "newer than supported" in str(error):
                raise UnsupportedSchemaVersion(str(error)) from error
            raise
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    @property
    def schema_version(self) -> int:
        """Return the highest migration version applied to this database."""

        return int(self._db.execute("PRAGMA user_version").fetchone()[0])

    @property
    def _db(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("ledger is closed")
        return self._connection

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._mutex:
            connection = self._db
            connection.execute("BEGIN IMMEDIATE")
            try:
                yield connection
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    @contextmanager
    def _read_transaction(self) -> Iterator[sqlite3.Connection]:
        with self._mutex:
            connection = self._db
            connection.execute("BEGIN")
            try:
                yield connection
                connection.commit()
            except BaseException:
                if connection.in_transaction:
                    connection.rollback()
                raise

    def save_project_config(self, config: ProjectConfig) -> str:
        """Persist a project configuration revision without rewriting history."""

        now = _now()
        with self._transaction() as connection:
            digest = self._ensure_project_config(connection, config, now)
            connection.execute(
                "UPDATE projects SET name = ?, path = ?, current_revision = ?, updated_at = ? "
                "WHERE project_id = ?",
                (config.name, config.path, config.settings_revision, _iso(now), config.id),
            )
            return digest

    def _ensure_project_config(
        self, connection: sqlite3.Connection, config: ProjectConfig, now: datetime
    ) -> str:
        payload = canonical_json(config)
        digest = content_hash(payload)
        project = connection.execute(
            "SELECT current_revision FROM projects WHERE project_id = ?", (config.id,)
        ).fetchone()
        if project is None:
            connection.execute(
                "INSERT INTO projects(project_id, name, path, current_revision, "
                "created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    config.id,
                    config.name,
                    config.path,
                    config.settings_revision,
                    _iso(now),
                    _iso(now),
                ),
            )
        elif project["current_revision"] == config.settings_revision:
            connection.execute(
                "UPDATE projects SET name = ?, path = ?, updated_at = ? WHERE project_id = ?",
                (config.name, config.path, _iso(now), config.id),
            )

        existing = connection.execute(
            "SELECT content_hash, payload FROM project_configs "
            "WHERE project_id = ? AND settings_revision = ?",
            (config.id, config.settings_revision),
        ).fetchone()
        if existing is not None:
            if existing["content_hash"] != digest or existing["payload"] != payload:
                raise ImmutableSpecificationConflict(
                    f"project {config.id} revision {config.settings_revision} is immutable"
                )
            return digest

        connection.execute(
            "INSERT INTO project_configs(project_id, settings_revision, schema_version, payload, "
            "content_hash, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                config.id,
                config.settings_revision,
                config.schema_version,
                payload,
                digest,
                _iso(now),
            ),
        )
        connection.execute(
            "UPDATE projects SET name = ?, path = ?, current_revision = ?, updated_at = ? "
            "WHERE project_id = ?",
            (config.name, config.path, config.settings_revision, _iso(now), config.id),
        )
        return digest

    def get_project_config(self, project_id: str, revision: str) -> ProjectConfig:
        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT payload FROM project_configs "
                "WHERE project_id = ? AND settings_revision = ?",
                (project_id, revision),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown project configuration {project_id}@{revision}")
            return ProjectConfig.model_validate(json.loads(row["payload"]))

    def create_run(
        self,
        run_id: str,
        project_config: ProjectConfig,
        spec: RunSpec,
        command_id: UUID,
        *,
        actor: str,
        occurred_at: datetime | None = None,
    ) -> CommandReceipt:
        """Commit project/run snapshots, initial projections and their first event."""

        now = occurred_at or _now()
        if spec.project.project_id != project_config.id:
            raise LedgerInvariantError("run specification and project configuration IDs differ")
        if spec.project.settings_revision != project_config.settings_revision:
            raise LedgerInvariantError("run specification references a different project revision")
        calculated_hash = content_hash(canonical_json(spec, exclude={"snapshot_hash"}))
        if spec.snapshot_hash != calculated_hash:
            raise LedgerInvariantError("run specification snapshot hash does not match its payload")

        request_hash = content_hash(
            canonical_json(
                {
                    "run_id": run_id,
                    "project_config": project_config,
                    "spec": spec,
                    "actor": actor,
                }
            )
        )
        with self._transaction() as connection:
            prior = self._existing_command(connection, command_id, request_hash)
            if prior is not None:
                return prior

            self._ensure_project_config(connection, project_config, now)
            current = connection.execute(
                "SELECT snapshot_hash, settings_revision, revision FROM runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()
            if current is not None:
                if (
                    current["snapshot_hash"] != spec.snapshot_hash
                    or current["settings_revision"] != project_config.settings_revision
                ):
                    raise ImmutableSpecificationConflict(
                        f"run ID {run_id} already has another spec"
                    )
                receipt = CommandReceipt(
                    command_id=command_id,
                    run_id=run_id,
                    outcome=CommandOutcome.ACCEPTED,
                    resulting_revision=current["revision"],
                    created_at=now,
                )
                self._save_receipt(connection, request_hash, receipt)
                return receipt

            spec_payload = canonical_json(spec)
            existing_spec = connection.execute(
                "SELECT payload FROM run_specs WHERE snapshot_hash = ?", (spec.snapshot_hash,)
            ).fetchone()
            if existing_spec is not None and existing_spec["payload"] != spec_payload:
                raise ImmutableSpecificationConflict(
                    "run snapshot hash collides with a different payload"
                )
            connection.execute(
                "INSERT OR IGNORE INTO run_specs(snapshot_hash, schema_version, "
                "payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (spec.snapshot_hash, spec.schema_version, spec_payload, _iso(now)),
            )

            initial_state = RunState(
                run_id=run_id,
                status=RunStatus.READY,
                revision=0,
                active_stages=[],
                attempts_used=0,
                elapsed_seconds=0,
            )
            connection.execute(
                "INSERT INTO runs(run_id, project_id, settings_revision, snapshot_hash, "
                "status, revision, "
                "active_stages, attempts_used, elapsed_seconds, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    project_config.id,
                    project_config.settings_revision,
                    spec.snapshot_hash,
                    initial_state.status.value,
                    initial_state.revision,
                    canonical_json(initial_state.active_stages),
                    initial_state.attempts_used,
                    initial_state.elapsed_seconds,
                    _iso(now),
                    _iso(now),
                ),
            )
            for stage in spec.workflow.stages:
                connection.execute(
                    "INSERT INTO stages(run_id, stage_id, definition, status, updated_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (run_id, stage.id, canonical_json(stage), StageStatus.PENDING.value, _iso(now)),
                )
            initial_event = RunStatusChangedEvent(
                event_id=uuid4(),
                run_id=run_id,
                occurred_at=now,
                actor=actor,
                kind=EventKind.RUN_STATUS_CHANGED,
                previous=None,
                current=initial_state.status,
                reason="run created",
            )
            sequences = self._append_events(connection, run_id, (initial_event,))
            receipt = CommandReceipt(
                command_id=command_id,
                run_id=run_id,
                outcome=CommandOutcome.ACCEPTED,
                resulting_revision=0,
                event_sequences=sequences,
                created_at=now,
            )
            self._save_receipt(connection, request_hash, receipt)
            return receipt

    def get_run(self, run_id: str) -> PersistedRun:
        with self._read_transaction() as connection:
            row = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise RunNotFound(run_id)
            project_row = connection.execute(
                "SELECT payload FROM project_configs "
                "WHERE project_id = ? AND settings_revision = ?",
                (row["project_id"], row["settings_revision"]),
            ).fetchone()
            spec_row = connection.execute(
                "SELECT payload FROM run_specs WHERE snapshot_hash = ?", (row["snapshot_hash"],)
            ).fetchone()
            if project_row is None or spec_row is None:
                raise LedgerInvariantError(f"run {run_id} references a missing immutable snapshot")
            project_config = ProjectConfig.model_validate(json.loads(project_row["payload"]))
            spec = RunSpec.model_validate(json.loads(spec_row["payload"]))
            state = RunState(
                run_id=run_id,
                status=RunStatus(row["status"]),
                revision=row["revision"],
                active_stages=json.loads(row["active_stages"]),
                attempts_used=row["attempts_used"],
                elapsed_seconds=row["elapsed_seconds"],
            )
            projection_rows = connection.execute(
                "SELECT stage_id, status, updated_at FROM stages WHERE run_id = ?",
                (run_id,),
            ).fetchall()
            stage_by_id = {
                item["stage_id"]: StageProjection(
                    stage_id=item["stage_id"],
                    status=item["status"],
                    updated_at=datetime.fromisoformat(item["updated_at"]),
                )
                for item in projection_rows
            }
            projections = tuple(stage_by_id[stage.id] for stage in spec.workflow.stages)
            return PersistedRun(
                run_id=run_id,
                project_config=project_config,
                spec=spec,
                state=state,
                stages=projections,
            )

    def get_attempt(self, attempt_id: str) -> PersistedAttempt:
        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT a.*, s.payload AS spec_payload FROM attempts a "
                "JOIN attempt_specs s ON s.spec_hash = a.spec_hash WHERE a.attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown attempt {attempt_id}")
            return PersistedAttempt(
                stage_id=row["stage_id"],
                slot_id=row["slot_id"],
                spec=AgentRunSpec.model_validate(json.loads(row["spec_payload"])),
                state=AttemptState.model_validate(json.loads(row["state_payload"])),
            )

    def apply(self, mutation: LedgerMutation) -> CommandReceipt:
        """Apply a revision-checked mutation, events, ownership and outbox atomically."""

        request_payload = mutation.model_dump(mode="json")
        request_payload.pop("command_id", None)
        request_payload.pop("occurred_at", None)
        request_hash = content_hash(canonical_json(request_payload))
        with self._transaction() as connection:
            prior = self._existing_command(connection, mutation.command_id, request_hash)
            if prior is not None:
                return prior
            run_row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (mutation.run_id,)
            ).fetchone()
            if run_row is None:
                raise RunNotFound(mutation.run_id)
            current_revision = int(run_row["revision"])
            if mutation.expected_revision != current_revision:
                receipt = CommandReceipt(
                    command_id=mutation.command_id,
                    run_id=mutation.run_id,
                    expected_revision=mutation.expected_revision,
                    outcome=CommandOutcome.REJECTED,
                    resulting_revision=current_revision,
                    reason=(
                        f"stale_revision: expected {mutation.expected_revision}, "
                        f"current {current_revision}"
                    ),
                    created_at=mutation.occurred_at,
                )
                self._save_receipt(connection, request_hash, receipt)
                return receipt

            if self._is_outbox_noop(connection, mutation):
                receipt = CommandReceipt(
                    command_id=mutation.command_id,
                    run_id=mutation.run_id,
                    expected_revision=mutation.expected_revision,
                    outcome=CommandOutcome.ACCEPTED,
                    resulting_revision=current_revision,
                    created_at=mutation.occurred_at,
                )
                self._save_receipt(connection, request_hash, receipt)
                return receipt

            original_state = self._state_from_row(run_row)
            current_state = original_state
            generated_events: list[Event] = []
            event_sequences = list(
                self._append_events(connection, mutation.run_id, mutation.events)
            )

            run_changes = (
                mutation.run_update.model_dump(exclude_none=True) if mutation.run_update else {}
            )
            state_data = current_state.model_dump(mode="python")
            state_data.update(run_changes)
            state_data["revision"] = current_revision + 1
            current_state = RunState.model_validate(state_data)
            if current_state.status != original_state.status and not self._has_matching_event(
                mutation.events, RunStatusChangedEvent, current_state.status
            ):
                generated_events.append(
                    RunStatusChangedEvent(
                        event_id=uuid4(),
                        run_id=mutation.run_id,
                        occurred_at=mutation.occurred_at,
                        actor=mutation.actor,
                        kind=EventKind.RUN_STATUS_CHANGED,
                        previous=original_state.status,
                        current=current_state.status,
                    )
                )

            connection.execute(
                "UPDATE runs SET status = ?, revision = ?, active_stages = ?, attempts_used = ?, "
                "elapsed_seconds = ?, updated_at = ? WHERE run_id = ?",
                (
                    current_state.status.value,
                    current_state.revision,
                    canonical_json(current_state.active_stages),
                    current_state.attempts_used,
                    current_state.elapsed_seconds,
                    _iso(mutation.occurred_at),
                    mutation.run_id,
                ),
            )

            for attempt_registration in mutation.attempt_creations:
                self._register_attempt(connection, mutation, attempt_registration, generated_events)
            for state in mutation.attempt_updates:
                self._update_attempt(connection, mutation, state, generated_events)

            for artifact_registration in mutation.artifacts:
                if self._insert_artifact_manifest(
                    connection, mutation.run_id, artifact_registration, mutation.occurred_at
                ):
                    generated_events.append(
                        ArtifactRecordedEvent(
                            event_id=uuid4(),
                            run_id=mutation.run_id,
                            occurred_at=mutation.occurred_at,
                            actor=mutation.actor,
                            kind=EventKind.ARTIFACT_RECORDED,
                            artifact=artifact_registration.artifact,
                        )
                    )

            for intent in mutation.outbox_actions:
                self._insert_outbox(connection, mutation, intent)
                if not self._has_matching_outbox_event(
                    mutation.events, intent.action_id, OutboxStatus.PENDING
                ):
                    generated_events.append(
                        OutboxStatusChangedEvent(
                            event_id=uuid4(),
                            run_id=mutation.run_id,
                            occurred_at=mutation.occurred_at,
                            actor=mutation.actor,
                            kind=EventKind.OUTBOX_STATUS_CHANGED,
                            action_id=intent.action_id,
                            previous=None,
                            current=OutboxStatus.PENDING,
                        )
                    )
            for outcome in mutation.outbox_outcomes:
                changed = self._apply_outbox_outcome(connection, mutation, outcome)
                if changed and not self._has_matching_outbox_event(
                    mutation.events, outcome.action_id, outcome.status
                ):
                    generated_events.append(
                        OutboxStatusChangedEvent(
                            event_id=uuid4(),
                            run_id=mutation.run_id,
                            occurred_at=mutation.occurred_at,
                            actor=mutation.actor,
                            kind=EventKind.OUTBOX_STATUS_CHANGED,
                            action_id=outcome.action_id,
                            previous=OutboxStatus.CLAIMED,
                            current=outcome.status,
                            result=outcome.result,
                        )
                    )

            for reservation in mutation.reservations:
                reservation_event = self._apply_reservation(connection, mutation, reservation)
                if reservation_event is not None:
                    generated_events.append(reservation_event)

            for update in mutation.stage_updates:
                row = connection.execute(
                    "SELECT status FROM stages WHERE run_id = ? AND stage_id = ?",
                    (mutation.run_id, update.stage_id),
                ).fetchone()
                if row is None:
                    raise LedgerInvariantError(
                        f"run {mutation.run_id} references missing stage {update.stage_id}"
                    )
                previous = StageStatus(row["status"])
                connection.execute(
                    "UPDATE stages SET status = ?, updated_at = ? "
                    "WHERE run_id = ? AND stage_id = ?",
                    (
                        update.status.value,
                        _iso(mutation.occurred_at),
                        mutation.run_id,
                        update.stage_id,
                    ),
                )
                if previous != update.status and not self._has_matching_stage_event(
                    mutation.events, update.stage_id, update.status
                ):
                    generated_events.append(
                        StageStatusChangedEvent(
                            event_id=uuid4(),
                            run_id=mutation.run_id,
                            occurred_at=mutation.occurred_at,
                            actor=mutation.actor,
                            kind=EventKind.STAGE_STATUS_CHANGED,
                            stage_id=update.stage_id,
                            previous=previous,
                            current=update.status,
                        )
                    )

            for handoff in mutation.handoffs:
                self._insert_handoff(connection, mutation.run_id, handoff, mutation.occurred_at)
                if not self._has_matching_handoff_event(mutation.events, handoff):
                    generated_events.append(
                        HandoffRecordedEvent(
                            event_id=uuid4(),
                            run_id=mutation.run_id,
                            occurred_at=mutation.occurred_at,
                            actor=mutation.actor,
                            kind=EventKind.HANDOFF_RECORDED,
                            handoff=handoff,
                        )
                    )
            for event in mutation.events:
                if isinstance(event, HandoffRecordedEvent):
                    self._insert_handoff(
                        connection, mutation.run_id, event.handoff, mutation.occurred_at
                    )

            event_sequences.extend(
                self._append_events(connection, mutation.run_id, tuple(generated_events))
            )
            receipt = CommandReceipt(
                command_id=mutation.command_id,
                run_id=mutation.run_id,
                expected_revision=mutation.expected_revision,
                outcome=CommandOutcome.ACCEPTED,
                resulting_revision=current_state.revision,
                event_sequences=tuple(event_sequences),
                created_at=mutation.occurred_at,
            )
            self._save_receipt(connection, request_hash, receipt)
            return receipt

    def _register_attempt(
        self,
        connection: sqlite3.Connection,
        mutation: LedgerMutation,
        registration: AttemptRegistration,
        generated_events: list[Event],
    ) -> None:
        spec = registration.spec
        state = registration.state
        if spec.run_id != mutation.run_id:
            raise LedgerInvariantError("attempt specification belongs to another run")
        run = connection.execute(
            "SELECT snapshot_hash FROM runs WHERE run_id = ?", (mutation.run_id,)
        ).fetchone()
        if run is None or spec.run_snapshot_hash != run["snapshot_hash"]:
            raise LedgerInvariantError("attempt specification references a different run snapshot")
        spec_payload = canonical_json(spec)
        spec_hash = content_hash(spec_payload)
        existing = connection.execute(
            "SELECT payload FROM attempt_specs WHERE spec_hash = ?", (spec_hash,)
        ).fetchone()
        if existing is not None and existing["payload"] != spec_payload:
            raise ImmutableSpecificationConflict("attempt specification hash collision")
        connection.execute(
            "INSERT OR IGNORE INTO attempt_specs(spec_hash, schema_version, payload, created_at) "
            "VALUES (?, ?, ?, ?)",
            (spec_hash, spec.schema_version, spec_payload, _iso(mutation.occurred_at)),
        )
        connection.execute(
            "INSERT INTO attempts(attempt_id, run_id, stage_id, slot_id, spec_hash, status, "
            "state_payload, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                spec.attempt_id,
                mutation.run_id,
                registration.stage_id,
                registration.slot_id,
                spec_hash,
                state.status.value,
                canonical_json(state),
                _iso(mutation.occurred_at),
                _iso(mutation.occurred_at),
            ),
        )
        if not self._has_matching_attempt_event(mutation.events, state.attempt_id, state.status):
            generated_events.append(
                AttemptStatusChangedEvent(
                    event_id=uuid4(),
                    run_id=mutation.run_id,
                    occurred_at=mutation.occurred_at,
                    actor=mutation.actor,
                    kind=EventKind.ATTEMPT_STATUS_CHANGED,
                    attempt_id=state.attempt_id,
                    previous=None,
                    current=state.status,
                )
            )

    def _update_attempt(
        self,
        connection: sqlite3.Connection,
        mutation: LedgerMutation,
        state: AttemptState,
        generated_events: list[Event],
    ) -> None:
        row = connection.execute(
            "SELECT status, state_payload FROM attempts WHERE attempt_id = ? AND run_id = ?",
            (state.attempt_id, mutation.run_id),
        ).fetchone()
        if row is None:
            raise LedgerInvariantError(f"run {mutation.run_id} has no attempt {state.attempt_id}")
        previous = AttemptStatus(row["status"])
        connection.execute(
            "UPDATE attempts SET status = ?, state_payload = ?, updated_at = ? "
            "WHERE attempt_id = ? AND run_id = ?",
            (
                state.status.value,
                canonical_json(state),
                _iso(mutation.occurred_at),
                state.attempt_id,
                mutation.run_id,
            ),
        )
        if previous != state.status and not self._has_matching_attempt_event(
            mutation.events, state.attempt_id, state.status
        ):
            generated_events.append(
                AttemptStatusChangedEvent(
                    event_id=uuid4(),
                    run_id=mutation.run_id,
                    occurred_at=mutation.occurred_at,
                    actor=mutation.actor,
                    kind=EventKind.ATTEMPT_STATUS_CHANGED,
                    attempt_id=state.attempt_id,
                    previous=previous,
                    current=state.status,
                )
            )

    def _insert_outbox(
        self, connection: sqlite3.Connection, mutation: LedgerMutation, intent: OutboxIntent
    ) -> None:
        payload = canonical_json(intent.payload)
        connection.execute(
            "INSERT INTO outbox_actions(action_id, action_key, run_id, command_id, kind, payload, "
            "status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(intent.action_id),
                intent.action_key,
                mutation.run_id,
                str(mutation.command_id),
                intent.kind,
                payload,
                OutboxStatus.PENDING.value,
                _iso(mutation.occurred_at),
            ),
        )

    def _apply_outbox_outcome(
        self,
        connection: sqlite3.Connection,
        mutation: LedgerMutation,
        change: OutboxOutcomeChange,
    ) -> bool:
        row = connection.execute(
            "SELECT status FROM outbox_actions WHERE action_id = ? AND run_id = ?",
            (str(change.action_id), mutation.run_id),
        ).fetchone()
        if row is None:
            raise LedgerInvariantError(f"outbox action {change.action_id} does not belong to run")
        previous = OutboxStatus(row["status"])
        if previous == change.status:
            return False
        if previous != OutboxStatus.CLAIMED:
            raise OutboxTransitionError(
                f"cannot move outbox action {change.action_id} from {previous.value} "
                f"to {change.status.value}"
            )
        connection.execute(
            "UPDATE outbox_actions SET status = ?, outcome_command_id = ?, result = ? "
            "WHERE action_id = ?",
            (
                change.status.value,
                str(mutation.command_id),
                change.result,
                str(change.action_id),
            ),
        )
        return True

    def _apply_reservation(
        self,
        connection: sqlite3.Connection,
        mutation: LedgerMutation,
        change: ReservationChange,
    ) -> ReservationStatusChangedEvent | None:
        if change.operation == ReservationOperation.RESERVE:
            if change.attempt_id is not None:
                attempt = connection.execute(
                    "SELECT run_id FROM attempts WHERE attempt_id = ?", (change.attempt_id,)
                ).fetchone()
                if attempt is None or attempt["run_id"] != mutation.run_id:
                    raise ReservationConflict("reservation attempt does not belong to this run")
            existing = connection.execute(
                "SELECT * FROM reservations WHERE reservation_key = ?", (change.reservation_key,)
            ).fetchone()
            if existing is not None:
                same = (
                    existing["reservation_id"] == change.reservation_id
                    and existing["run_id"] == mutation.run_id
                    and existing["attempt_id"] == change.attempt_id
                    and existing["scope"] == change.scope
                    and existing["resource_key"] == change.resource_key
                )
                if same and existing["status"] == ReservationStatus.HELD.value:
                    return None
                raise ReservationConflict(
                    f"reservation key {change.reservation_key} already exists"
                )
            connection.execute(
                "INSERT INTO reservations(reservation_id, reservation_key, run_id, "
                "attempt_id, scope, "
                "resource_key, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    change.reservation_id,
                    change.reservation_key,
                    mutation.run_id,
                    change.attempt_id,
                    change.scope,
                    change.resource_key,
                    ReservationStatus.HELD.value,
                    _iso(mutation.occurred_at),
                ),
            )
            return ReservationStatusChangedEvent(
                event_id=uuid4(),
                run_id=mutation.run_id,
                occurred_at=mutation.occurred_at,
                actor=mutation.actor,
                kind=EventKind.RESERVATION_STATUS_CHANGED,
                reservation_id=change.reservation_id,
                reservation_key=change.reservation_key,
                scope=change.scope or "run",
                resource_key=change.resource_key or mutation.run_id,
                previous=None,
                current=ReservationStatus.HELD,
                attempt_id=change.attempt_id,
            )

        row = connection.execute(
            "SELECT * FROM reservations WHERE reservation_id = ? AND reservation_key = ? "
            "AND run_id = ?",
            (change.reservation_id, change.reservation_key, mutation.run_id),
        ).fetchone()
        if row is None:
            raise ReservationConflict(f"reservation {change.reservation_id} does not exist")
        if row["status"] == ReservationStatus.RELEASED.value:
            return None
        attempt_id = row["attempt_id"]
        if attempt_id is not None:
            attempt = connection.execute(
                "SELECT status FROM attempts WHERE attempt_id = ? AND run_id = ?",
                (attempt_id, mutation.run_id),
            ).fetchone()
            if attempt is None or attempt["status"] not in {
                AttemptStatus.SUCCEEDED.value,
                AttemptStatus.FAILED.value,
                AttemptStatus.TIMED_OUT.value,
                AttemptStatus.CANCELLED.value,
            }:
                raise ReservationConflict("attempt ownership can be released only after settlement")
        connection.execute(
            "UPDATE reservations SET status = ?, released_at = ? WHERE reservation_id = ?",
            (ReservationStatus.RELEASED.value, _iso(mutation.occurred_at), change.reservation_id),
        )
        return ReservationStatusChangedEvent(
            event_id=uuid4(),
            run_id=mutation.run_id,
            occurred_at=mutation.occurred_at,
            actor=mutation.actor,
            kind=EventKind.RESERVATION_STATUS_CHANGED,
            reservation_id=row["reservation_id"],
            reservation_key=row["reservation_key"],
            scope=row["scope"],
            resource_key=row["resource_key"],
            previous=ReservationStatus.HELD,
            current=ReservationStatus.RELEASED,
            attempt_id=attempt_id,
        )

    def _insert_handoff(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        handoff: Any,
        occurred_at: datetime,
    ) -> None:
        source_attempt = connection.execute(
            "SELECT run_id FROM attempts WHERE attempt_id = ?", (handoff.source_attempt_id,)
        ).fetchone()
        if source_attempt is None or source_attempt["run_id"] != run_id:
            raise LedgerInvariantError("handoff source attempt does not belong to this run")
        expected_parts = (
            "runs",
            run_id,
            "attempts",
            handoff.source_attempt_id,
            "artifacts",
            handoff.content_hash,
        )
        relative = PurePosixPath(handoff.relative_path)
        if (
            relative.is_absolute()
            or "\\" in handoff.relative_path
            or relative.parts != expected_parts
            or len(handoff.content_hash) != 64
            or any(char not in "0123456789abcdef" for char in handoff.content_hash)
        ):
            raise LedgerInvariantError(
                "handoff must reference a managed content-addressed artifact"
            )
        artifact = connection.execute(
            "SELECT 1 FROM artifact_manifests WHERE run_id = ? AND attempt_id = ? "
            "AND relative_path = ? AND content_hash = ?",
            (run_id, handoff.source_attempt_id, handoff.relative_path, handoff.content_hash),
        ).fetchone()
        if artifact is None:
            raise LedgerInvariantError("handoff source artifact has no durable manifest")
        payload = canonical_json(handoff)
        handoff_id = content_hash(payload)
        connection.execute(
            "INSERT OR IGNORE INTO handoffs(handoff_id, run_id, attempt_id, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (handoff_id, run_id, handoff.source_attempt_id, payload, _iso(occurred_at)),
        )

    def _insert_artifact_manifest(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        registration: ArtifactRegistration,
        occurred_at: datetime,
    ) -> bool:
        artifact = registration.artifact
        expected_parts = (
            "runs",
            run_id,
            "attempts",
            artifact.attempt_id,
            "artifacts",
            artifact.content_hash,
        )
        relative = PurePosixPath(artifact.relative_path)
        if (
            relative.is_absolute()
            or "\\" in artifact.relative_path
            or relative.parts != expected_parts
            or any(part in {"", ".", ".."} for part in relative.parts)
        ):
            raise LedgerInvariantError(
                "artifact path is outside the managed run artifact directory"
            )
        if len(artifact.content_hash) != 64 or any(
            char not in "0123456789abcdef" for char in artifact.content_hash
        ):
            raise LedgerInvariantError("artifact content hash must be a lowercase SHA-256 digest")
        attempt = connection.execute(
            "SELECT run_id FROM attempts WHERE attempt_id = ?", (artifact.attempt_id,)
        ).fetchone()
        if attempt is None or attempt["run_id"] != run_id:
            raise LedgerInvariantError("artifact attempt does not belong to this run")
        payload = canonical_json(artifact)
        existing = connection.execute(
            "SELECT payload, size_bytes FROM artifact_manifests WHERE artifact_id = ?",
            (artifact.id,),
        ).fetchone()
        if existing is not None:
            if existing["payload"] != payload or existing["size_bytes"] != registration.size_bytes:
                raise ImmutableSpecificationConflict(f"artifact ID {artifact.id} is immutable")
            return False
        connection.execute(
            "INSERT INTO artifact_manifests(artifact_id, run_id, attempt_id, relative_path, "
            "content_hash, size_bytes, schema_version, payload, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                artifact.id,
                run_id,
                artifact.attempt_id,
                artifact.relative_path,
                artifact.content_hash,
                registration.size_bytes,
                artifact.schema_version,
                payload,
                _iso(occurred_at),
            ),
        )
        return True

    def _artifact_manifest_from_row(self, row: sqlite3.Row) -> ArtifactManifest:
        return ArtifactManifest(
            artifact=Artifact.model_validate(json.loads(row["payload"])),
            size_bytes=row["size_bytes"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _append_events(
        self,
        connection: sqlite3.Connection,
        run_id: str,
        events: tuple[Event, ...],
    ) -> tuple[int, ...]:
        if not events:
            return ()
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence), 0) AS last_sequence FROM events WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        sequence = int(row["last_sequence"])
        appended: list[int] = []
        for event in events:
            if event.run_id != run_id:
                raise LedgerInvariantError("event run ID does not match its transaction")
            if event.sequence is not None:
                raise LedgerInvariantError("event sequence is assigned by the ledger")
            sequence += 1
            payload = event.model_dump(mode="json")
            payload["sequence"] = sequence
            persisted = EVENT_ADAPTER.validate_python(payload)
            serialized = canonical_json(persisted)
            connection.execute(
                "INSERT INTO events(run_id, sequence, event_id, schema_version, kind, occurred_at, "
                "cause_event_id, payload) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    sequence,
                    str(event.event_id),
                    event.schema_version,
                    event.kind.value,
                    _iso(event.occurred_at),
                    str(event.cause_event_id) if event.cause_event_id else None,
                    serialized,
                ),
            )
            if isinstance(event, InterventionRequestedEvent):
                connection.execute(
                    "INSERT INTO interventions(command_id, run_id, payload, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        str(event.intervention.command_id),
                        run_id,
                        canonical_json(event.intervention),
                        _iso(event.occurred_at),
                    ),
                )
            appended.append(sequence)
        return tuple(appended)

    def _state_from_row(self, row: sqlite3.Row) -> RunState:
        return RunState(
            run_id=row["run_id"],
            status=row["status"],
            revision=row["revision"],
            active_stages=json.loads(row["active_stages"]),
            attempts_used=row["attempts_used"],
            elapsed_seconds=row["elapsed_seconds"],
        )

    def _save_receipt(
        self,
        connection: sqlite3.Connection,
        request_hash: str,
        receipt: CommandReceipt,
    ) -> None:
        connection.execute(
            "INSERT INTO command_receipts(command_id, run_id, request_hash, outcome, "
            "result_payload, "
            "created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                str(receipt.command_id),
                receipt.run_id,
                request_hash,
                receipt.outcome.value,
                canonical_json(receipt),
                _iso(receipt.created_at),
            ),
        )

    def _existing_command(
        self, connection: sqlite3.Connection, command_id: UUID, request_hash: str
    ) -> CommandReceipt | None:
        row = connection.execute(
            "SELECT request_hash, result_payload FROM command_receipts WHERE command_id = ?",
            (str(command_id),),
        ).fetchone()
        if row is None:
            return None
        if row["request_hash"] != request_hash:
            raise CommandIdConflict(f"command ID {command_id} was already used for another request")
        return CommandReceipt.model_validate(json.loads(row["result_payload"]))

    def _is_outbox_noop(self, connection: sqlite3.Connection, mutation: LedgerMutation) -> bool:
        if (
            not mutation.outbox_outcomes
            or mutation.run_update is not None
            or mutation.stage_updates
            or mutation.attempt_creations
            or mutation.attempt_updates
            or mutation.events
            or mutation.outbox_actions
            or mutation.reservations
            or mutation.handoffs
            or mutation.artifacts
        ):
            return False
        for change in mutation.outbox_outcomes:
            row = connection.execute(
                "SELECT status FROM outbox_actions WHERE action_id = ? AND run_id = ?",
                (str(change.action_id), mutation.run_id),
            ).fetchone()
            if row is None or row["status"] != change.status.value:
                return False
        return True

    def get_command_receipt(self, command_id: UUID) -> CommandReceipt | None:
        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT result_payload FROM command_receipts WHERE command_id = ?",
                (str(command_id),),
            ).fetchone()
            if row is None:
                return None
            return CommandReceipt.model_validate(json.loads(row["result_payload"]))

    def _acquire_owner(self, owner_id: str, acquired_at: datetime) -> OwnerLease:
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT generation FROM owner_state WHERE singleton = 1"
            ).fetchone()
            if row is None:
                raise LedgerInvariantError("coordinator owner state is missing")
            generation = int(row["generation"]) + 1
            connection.execute(
                "UPDATE owner_state SET generation = ?, owner_id = ?, acquired_at = ?, "
                "released_at = NULL "
                "WHERE singleton = 1",
                (generation, owner_id, _iso(acquired_at)),
            )
            return OwnerLease(generation=generation, owner_id=owner_id, acquired_at=acquired_at)

    def _release_owner(self, lease: OwnerLease, released_at: datetime) -> None:
        with self._transaction() as connection:
            cursor = connection.execute(
                "UPDATE owner_state SET released_at = ? WHERE singleton = 1 AND generation = ? "
                "AND owner_id = ? AND released_at IS NULL",
                (_iso(released_at), lease.generation, lease.owner_id),
            )
            if cursor.rowcount != 1:
                raise LedgerInvariantError("coordinator owner lease is no longer current")

    def list_events(self, run_id: str, after_sequence: int = 0) -> tuple[Event, ...]:
        with self._read_transaction() as connection:
            if (
                connection.execute("SELECT 1 FROM runs WHERE run_id = ?", (run_id,)).fetchone()
                is None
            ):
                raise RunNotFound(run_id)
            rows = connection.execute(
                "SELECT payload FROM events WHERE run_id = ? AND sequence > ? ORDER BY sequence",
                (run_id, after_sequence),
            ).fetchall()
            return tuple(EVENT_ADAPTER.validate_python(json.loads(row["payload"])) for row in rows)

    def list_interventions(self, run_id: str) -> tuple[Intervention, ...]:
        adapter: TypeAdapter[Intervention] = TypeAdapter(Intervention)
        with self._read_transaction() as connection:
            rows = connection.execute(
                "SELECT payload FROM interventions WHERE run_id = ? "
                "ORDER BY created_at, command_id",
                (run_id,),
            ).fetchall()
            return tuple(adapter.validate_python(json.loads(row["payload"])) for row in rows)

    def list_handoffs(self, run_id: str) -> tuple[Handoff, ...]:
        with self._read_transaction() as connection:
            rows = connection.execute(
                "SELECT payload FROM handoffs WHERE run_id = ? ORDER BY created_at, handoff_id",
                (run_id,),
            ).fetchall()
            return tuple(Handoff.model_validate(json.loads(row["payload"])) for row in rows)

    def get_outbox_action(self, action_id: UUID) -> OutboxAction:
        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT * FROM outbox_actions WHERE action_id = ?", (str(action_id),)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown outbox action {action_id}")
            return self._outbox_from_row(row)

    def get_artifact_manifest(self, artifact_id: str) -> ArtifactManifest | None:
        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT * FROM artifact_manifests WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            return self._artifact_manifest_from_row(row) if row is not None else None

    def record_artifact_manifest(
        self,
        publication: ArtifactPublication,
        artifact: Artifact,
        size_bytes: int,
    ) -> ArtifactManifest:
        """Publish an artifact manifest and event under the caller's expected run revision."""

        if (
            artifact.id != publication.artifact_id
            or artifact.attempt_id != publication.attempt_id
            or artifact.input_revision != publication.input_revision
            or artifact.workspace_revision != publication.workspace_revision
            or artifact.schema_id != publication.schema_id
        ):
            raise LedgerInvariantError("artifact metadata does not match its publication command")
        receipt = self.apply(
            LedgerMutation(
                command_id=publication.command_id,
                run_id=publication.run_id,
                expected_revision=publication.expected_run_revision,
                actor=publication.actor,
                occurred_at=publication.occurred_at,
                artifacts=(ArtifactRegistration(artifact=artifact, size_bytes=size_bytes),),
            )
        )
        if receipt.outcome != CommandOutcome.ACCEPTED:
            raise LedgerInvariantError(receipt.reason or "artifact publication was rejected")
        manifest = self.get_artifact_manifest(artifact.id)
        if manifest is None:
            raise LedgerInvariantError("artifact command committed without a manifest")
        return manifest

    def list_outbox_actions(self, run_id: str | None = None) -> tuple[OutboxAction, ...]:
        with self._read_transaction() as connection:
            if run_id is None:
                rows = connection.execute(
                    "SELECT * FROM outbox_actions ORDER BY created_at, action_id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM outbox_actions WHERE run_id = ? ORDER BY created_at, action_id",
                    (run_id,),
                ).fetchall()
            return tuple(self._outbox_from_row(row) for row in rows)

    def _outbox_from_row(self, row: sqlite3.Row) -> OutboxAction:
        return OutboxAction(
            action_id=UUID(row["action_id"]),
            action_key=row["action_key"],
            run_id=row["run_id"],
            command_id=UUID(row["command_id"]),
            kind=row["kind"],
            payload=json.loads(row["payload"]),
            status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            claimed_at=datetime.fromisoformat(row["claimed_at"]) if row["claimed_at"] else None,
            claimed_by=row["claimed_by"],
            outcome_command_id=(
                UUID(row["outcome_command_id"]) if row["outcome_command_id"] else None
            ),
            result=row["result"],
        )

    def claim_next_outbox(
        self, owner_id: str, occurred_at: datetime | None = None
    ) -> OutboxAction | None:
        """Mark one pending action claimed; claimed/unknown actions are never selected again."""

        now = occurred_at or _now()
        with self._transaction() as connection:
            row = connection.execute(
                "SELECT * FROM outbox_actions WHERE status = ? "
                "ORDER BY created_at, action_id LIMIT 1",
                (OutboxStatus.PENDING.value,),
            ).fetchone()
            if row is None:
                return None
            run_row = connection.execute(
                "SELECT * FROM runs WHERE run_id = ?", (row["run_id"],)
            ).fetchone()
            if run_row is None:
                raise LedgerInvariantError("outbox action references a missing run")
            connection.execute(
                "UPDATE outbox_actions SET status = ?, claimed_at = ?, claimed_by = ? "
                "WHERE action_id = ? AND status = ?",
                (
                    OutboxStatus.CLAIMED.value,
                    _iso(now),
                    owner_id,
                    row["action_id"],
                    OutboxStatus.PENDING.value,
                ),
            )
            connection.execute(
                "UPDATE runs SET revision = revision + 1, updated_at = ? WHERE run_id = ?",
                (_iso(now), row["run_id"]),
            )
            event = OutboxStatusChangedEvent(
                event_id=uuid4(),
                run_id=row["run_id"],
                occurred_at=now,
                actor=owner_id,
                kind=EventKind.OUTBOX_STATUS_CHANGED,
                action_id=UUID(row["action_id"]),
                previous=OutboxStatus.PENDING,
                current=OutboxStatus.CLAIMED,
                result="claimed for delivery",
            )
            self._append_events(connection, row["run_id"], (event,))
            refreshed = connection.execute(
                "SELECT * FROM outbox_actions WHERE action_id = ?", (row["action_id"],)
            ).fetchone()
            return self._outbox_from_row(refreshed)

    def record_outbox_outcome(
        self,
        action_id: UUID,
        command_id: UUID,
        expected_revision: int,
        status: OutboxStatus,
        *,
        result: str | None,
        actor: str,
        occurred_at: datetime | None = None,
    ) -> CommandReceipt:
        """Persist a delivery outcome through the same revision-checked mutation seam."""

        with self._read_transaction() as connection:
            row = connection.execute(
                "SELECT run_id FROM outbox_actions WHERE action_id = ?", (str(action_id),)
            ).fetchone()
            if row is None:
                raise KeyError(f"unknown outbox action {action_id}")
            run_id = row["run_id"]
        return self.apply(
            LedgerMutation(
                command_id=command_id,
                run_id=run_id,
                expected_revision=expected_revision,
                actor=actor,
                occurred_at=occurred_at or _now(),
                outbox_outcomes=(
                    OutboxOutcomeChange(action_id=action_id, status=status, result=result),
                ),
            )
        )

    def list_reservations(self, run_id: str) -> tuple[ReservationRecord, ...]:
        with self._read_transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM reservations WHERE run_id = ? ORDER BY created_at, reservation_id",
                (run_id,),
            ).fetchall()
            return tuple(
                ReservationRecord(
                    reservation_id=row["reservation_id"],
                    reservation_key=row["reservation_key"],
                    run_id=row["run_id"],
                    attempt_id=row["attempt_id"],
                    scope=row["scope"],
                    resource_key=row["resource_key"],
                    status=row["status"],
                    created_at=datetime.fromisoformat(row["created_at"]),
                    released_at=(
                        datetime.fromisoformat(row["released_at"]) if row["released_at"] else None
                    ),
                )
                for row in rows
            )

    def _has_matching_event(
        self, events: tuple[Event, ...], event_type: type[Any], current: Any
    ) -> bool:
        return any(isinstance(event, event_type) and event.current == current for event in events)

    def _has_matching_stage_event(
        self, events: tuple[Event, ...], stage_id: str, current: StageStatus
    ) -> bool:
        return any(
            isinstance(event, StageStatusChangedEvent)
            and event.stage_id == stage_id
            and event.current == current
            for event in events
        )

    def _has_matching_attempt_event(
        self, events: tuple[Event, ...], attempt_id: str, current: AttemptStatus
    ) -> bool:
        return any(
            isinstance(event, AttemptStatusChangedEvent)
            and event.attempt_id == attempt_id
            and event.current == current
            for event in events
        )

    def _has_matching_outbox_event(
        self, events: tuple[Event, ...], action_id: UUID, current: OutboxStatus
    ) -> bool:
        return any(
            isinstance(event, OutboxStatusChangedEvent)
            and event.action_id == action_id
            and event.current == current
            for event in events
        )

    def _has_matching_handoff_event(self, events: tuple[Event, ...], handoff: Any) -> bool:
        return any(
            isinstance(event, HandoffRecordedEvent) and event.handoff == handoff for event in events
        )

    def close(self) -> None:
        with self._mutex:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def __enter__(self) -> Self:
        if self._closed:
            raise RuntimeError("ledger is closed")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
