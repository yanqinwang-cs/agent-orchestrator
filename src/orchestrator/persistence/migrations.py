"""Versioned SQLite schema migrations."""

import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime

Migration = tuple[int, str, Callable[[sqlite3.Connection], None]]


def _create_v1(connection: sqlite3.Connection) -> None:
    script = """
        CREATE TABLE schema_migrations (
            version INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE projects (
            project_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            path TEXT NOT NULL,
            current_revision TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE project_configs (
            project_id TEXT NOT NULL,
            settings_revision TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            payload TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (project_id, settings_revision),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        CREATE TRIGGER project_configs_immutable_update BEFORE UPDATE ON project_configs
        BEGIN SELECT RAISE(ABORT, 'immutable project configuration'); END;
        CREATE TRIGGER project_configs_immutable_delete BEFORE DELETE ON project_configs
        BEGIN SELECT RAISE(ABORT, 'immutable project configuration'); END;

        CREATE TABLE run_specs (
            snapshot_hash TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER run_specs_immutable_update BEFORE UPDATE ON run_specs
        BEGIN SELECT RAISE(ABORT, 'immutable run specification'); END;
        CREATE TRIGGER run_specs_immutable_delete BEFORE DELETE ON run_specs
        BEGIN SELECT RAISE(ABORT, 'immutable run specification'); END;
        CREATE TABLE runs (
            run_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            settings_revision TEXT NOT NULL,
            snapshot_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            revision INTEGER NOT NULL CHECK (revision >= 0),
            active_stages TEXT NOT NULL,
            attempts_used INTEGER NOT NULL CHECK (attempts_used >= 0),
            elapsed_seconds REAL NOT NULL CHECK (elapsed_seconds >= 0),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (project_id, settings_revision)
                REFERENCES project_configs(project_id, settings_revision),
            FOREIGN KEY (snapshot_hash) REFERENCES run_specs(snapshot_hash)
        );
        CREATE TABLE stages (
            run_id TEXT NOT NULL,
            stage_id TEXT NOT NULL,
            definition TEXT NOT NULL,
            status TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (run_id, stage_id),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        CREATE TRIGGER stage_definitions_immutable BEFORE UPDATE OF definition ON stages
        BEGIN SELECT RAISE(ABORT, 'immutable stage definition'); END;
        CREATE TABLE attempt_specs (
            spec_hash TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TRIGGER attempt_specs_immutable_update BEFORE UPDATE ON attempt_specs
        BEGIN SELECT RAISE(ABORT, 'immutable attempt specification'); END;
        CREATE TRIGGER attempt_specs_immutable_delete BEFORE DELETE ON attempt_specs
        BEGIN SELECT RAISE(ABORT, 'immutable attempt specification'); END;
        CREATE TABLE attempts (
            attempt_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            stage_id TEXT NOT NULL,
            slot_id TEXT NOT NULL,
            spec_hash TEXT NOT NULL,
            status TEXT NOT NULL,
            state_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (run_id, stage_id) REFERENCES stages(run_id, stage_id),
            FOREIGN KEY (spec_hash) REFERENCES attempt_specs(spec_hash)
        );
        CREATE TABLE events (
            run_id TEXT NOT NULL,
            sequence INTEGER NOT NULL CHECK (sequence > 0),
            event_id TEXT NOT NULL UNIQUE,
            schema_version INTEGER NOT NULL,
            kind TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            cause_event_id TEXT,
            payload TEXT NOT NULL,
            PRIMARY KEY (run_id, sequence),
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        CREATE TRIGGER events_no_update BEFORE UPDATE ON events
        BEGIN SELECT RAISE(ABORT, 'event journal is append-only'); END;
        CREATE TRIGGER events_no_delete BEFORE DELETE ON events
        BEGIN SELECT RAISE(ABORT, 'event journal is append-only'); END;
        CREATE TABLE interventions (
            command_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE command_receipts (
            command_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            request_hash TEXT NOT NULL,
            outcome TEXT NOT NULL CHECK (outcome IN ('accepted', 'rejected')),
            result_payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        CREATE TABLE outbox_actions (
            action_id TEXT PRIMARY KEY,
            action_key TEXT NOT NULL UNIQUE,
            run_id TEXT NOT NULL,
            command_id TEXT NOT NULL,
            kind TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL CHECK (
                status IN ('pending', 'claimed', 'acknowledged', 'rejected', 'unknown')
            ),
            created_at TEXT NOT NULL,
            claimed_at TEXT,
            claimed_by TEXT,
            outcome_command_id TEXT,
            result TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE
        );
        CREATE INDEX outbox_pending_order ON outbox_actions(status, created_at, action_id);
        CREATE TRIGGER outbox_intent_immutable BEFORE UPDATE OF action_id, action_key, run_id,
            command_id, kind, payload, created_at ON outbox_actions
        BEGIN SELECT RAISE(ABORT, 'immutable outbox intent'); END;

        CREATE TABLE reservations (
            reservation_id TEXT PRIMARY KEY,
            reservation_key TEXT NOT NULL UNIQUE,
            run_id TEXT NOT NULL,
            attempt_id TEXT,
            scope TEXT NOT NULL,
            resource_key TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('held', 'released')),
            created_at TEXT NOT NULL,
            released_at TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
        );
        CREATE INDEX reservations_by_run_status ON reservations(run_id, status);
        CREATE TRIGGER reservation_identity_immutable BEFORE UPDATE OF reservation_id,
            reservation_key, run_id, attempt_id, scope, resource_key, created_at ON reservations
        BEGIN SELECT RAISE(ABORT, 'immutable reservation identity'); END;

        CREATE TABLE handoffs (
            handoff_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
        );
        CREATE TRIGGER handoffs_no_update BEFORE UPDATE ON handoffs
        BEGIN SELECT RAISE(ABORT, 'immutable handoff'); END;
        CREATE TRIGGER handoffs_no_delete BEFORE DELETE ON handoffs
        BEGIN SELECT RAISE(ABORT, 'immutable handoff'); END;
        CREATE TABLE artifact_manifests (
            artifact_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            attempt_id TEXT NOT NULL,
            relative_path TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
            schema_version INTEGER NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (run_id) REFERENCES runs(run_id) ON DELETE CASCADE,
            FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
        );
        CREATE TRIGGER artifact_manifests_immutable_update BEFORE UPDATE ON artifact_manifests
        BEGIN SELECT RAISE(ABORT, 'immutable artifact manifest'); END;
        CREATE TRIGGER artifact_manifests_immutable_delete BEFORE DELETE ON artifact_manifests
        BEGIN SELECT RAISE(ABORT, 'immutable artifact manifest'); END;

        CREATE TABLE owner_state (
            singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
            generation INTEGER NOT NULL CHECK (generation >= 0),
            owner_id TEXT,
            acquired_at TEXT,
            released_at TEXT
        );
        INSERT INTO owner_state(singleton, generation) VALUES (1, 0);
        """
    statement = ""
    for line in script.splitlines(keepends=True):
        statement += line
        if sqlite3.complete_statement(statement):
            if statement.strip():
                connection.execute(statement)
            statement = ""
    if statement.strip():
        raise RuntimeError("incomplete SQL in the durable ledger migration")


MIGRATIONS: tuple[Migration, ...] = ((1, "durable-run-ledger", _create_v1),)
CURRENT_SCHEMA_VERSION = MIGRATIONS[-1][0]


def apply_migrations(connection: sqlite3.Connection) -> int:
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current_version > CURRENT_SCHEMA_VERSION:
        raise ValueError(
            f"database schema version {current_version} is newer than supported "
            f"version {CURRENT_SCHEMA_VERSION}"
        )

    for version, name, migration in MIGRATIONS:
        if version <= current_version:
            continue
        connection.execute("BEGIN EXCLUSIVE")
        try:
            migration(connection)
            applied_at = datetime.now(UTC).isoformat()
            connection.execute(
                "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, applied_at),
            )
            connection.execute(f"PRAGMA user_version = {version}")
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    return CURRENT_SCHEMA_VERSION
