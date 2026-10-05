"""SQLite persistence for immutable catalog versions and saved composition revisions."""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from agent_lab.catalog import BUILTIN_CATALOG, SeedResource
from agent_lab.domain import (
    CatalogResource,
    CompositionBinding,
    CompositionDraft,
    CompositionNotFoundError,
    CompositionRevision,
    MissingBindingError,
    ModelSettings,
    ResourceDefinition,
    ResourceKind,
    ResourceVersion,
    SavedComposition,
    StaleCompositionError,
)
from agent_lab.identity import sha256_json

SCHEMA_VERSION = 2

_SCHEMA = """
CREATE TABLE IF NOT EXISTS catalog_definitions (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog_versions (
    resource_id TEXT NOT NULL,
    version TEXT NOT NULL,
    body TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    digest TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (resource_id, version),
    FOREIGN KEY (resource_id) REFERENCES catalog_definitions(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS compositions (
    id TEXT PRIMARY KEY,
    current_revision INTEGER NOT NULL CHECK (current_revision >= 1),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS composition_revisions (
    composition_id TEXT NOT NULL,
    revision INTEGER NOT NULL CHECK (revision >= 1),
    schema_version INTEGER NOT NULL CHECK (schema_version >= 1),
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    instructions TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (composition_id, revision),
    FOREIGN KEY (composition_id) REFERENCES compositions(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS composition_models (
    composition_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    slot TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    parameters_json TEXT NOT NULL,
    PRIMARY KEY (composition_id, revision, slot),
    FOREIGN KEY (composition_id, revision)
        REFERENCES composition_revisions(composition_id, revision) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS composition_bindings (
    composition_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    binding_target TEXT NOT NULL,
    binding_ordinal INTEGER NOT NULL CHECK (binding_ordinal >= 0),
    resource_id TEXT NOT NULL,
    resource_version TEXT NOT NULL,
    resource_name TEXT NOT NULL,
    resource_kind TEXT NOT NULL,
    version_digest TEXT NOT NULL,
    PRIMARY KEY (composition_id, revision, binding_target, binding_ordinal),
    FOREIGN KEY (composition_id, revision)
        REFERENCES composition_revisions(composition_id, revision) ON DELETE RESTRICT,
    FOREIGN KEY (resource_id, resource_version)
        REFERENCES catalog_versions(resource_id, version) ON DELETE RESTRICT
);

CREATE TRIGGER IF NOT EXISTS catalog_definition_identity_no_update
BEFORE UPDATE OF id, kind ON catalog_definitions
BEGIN
    SELECT RAISE(ABORT, 'catalog definition identity is immutable');
END;

CREATE TRIGGER IF NOT EXISTS catalog_versions_no_update
BEFORE UPDATE ON catalog_versions
BEGIN
    SELECT RAISE(ABORT, 'catalog versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS catalog_versions_no_delete
BEFORE DELETE ON catalog_versions
BEGIN
    SELECT RAISE(ABORT, 'catalog versions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_revisions_no_update
BEFORE UPDATE ON composition_revisions
BEGIN
    SELECT RAISE(ABORT, 'composition revisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_revisions_no_delete
BEFORE DELETE ON composition_revisions
BEGIN
    SELECT RAISE(ABORT, 'composition revisions are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_bindings_no_update
BEFORE UPDATE ON composition_bindings
BEGIN
    SELECT RAISE(ABORT, 'composition bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_bindings_no_delete
BEFORE DELETE ON composition_bindings
BEGIN
    SELECT RAISE(ABORT, 'composition bindings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_models_no_update
BEFORE UPDATE ON composition_models
BEGIN
    SELECT RAISE(ABORT, 'composition model settings are immutable');
END;

CREATE TRIGGER IF NOT EXISTS composition_models_no_delete
BEFORE DELETE ON composition_models
BEGIN
    SELECT RAISE(ABORT, 'composition model settings are immutable');
END;
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _version_digest(resource_id: str, version: str, body: str, metadata: dict[str, str]) -> str:
    return sha256_json(
        {
            "resource_id": resource_id,
            "version": version,
            "body": body,
            "metadata": metadata,
        }
    )


def _composition_digest(
    *,
    name: str,
    description: str,
    instructions: str,
    bindings: Sequence[CompositionBinding],
    model_settings: Sequence[ModelSettings],
) -> str:
    return sha256_json(
        {
            "schema_version": 1,
            "name": name,
            "description": description,
            "instructions": instructions,
            "bindings": [
                {
                    "target": item.target,
                    "ordinal": item.ordinal,
                    "resource_id": item.resource_id,
                    "version": item.version,
                    "digest": item.digest,
                    "name": item.name,
                    "kind": item.kind.value,
                }
                for item in sorted(bindings, key=lambda item: (item.target, item.ordinal))
            ],
            "model_settings": [
                item.model_dump(mode="json")
                for item in sorted(model_settings, key=lambda item: item.slot)
            ],
        }
    )


class CatalogIntegrityError(RuntimeError):
    """A built-in catalog version conflicts with previously persisted bytes."""


class PersistenceIntegrityError(RuntimeError):
    """Persisted immutable content does not match its recorded digest."""


class SQLiteStore:
    """Own the local SQLite schema and all catalog/composition transactions."""

    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        if self.database != ":memory:":
            self.database = str(Path(self.database).expanduser())
            Path(self.database).parent.mkdir(parents=True, exist_ok=True)
            self._secure_database_files()
        else:
            raise ValueError("SQLiteStore requires a file-backed database for durable persistence.")
        self.initialize()

    def _connect(self) -> sqlite3.Connection:
        self._secure_database_files()
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _secure_database_files(self) -> None:
        descriptor = os.open(self.database, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            os.fchmod(descriptor, 0o600)
        finally:
            os.close(descriptor)
        for suffix in ("-journal", "-wal", "-shm"):
            try:
                os.chmod(f"{self.database}{suffix}", 0o600)
            except FileNotFoundError:
                pass

    def initialize(self) -> None:
        with self._connect() as connection:
            version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            if version not in (0, SCHEMA_VERSION):
                raise RuntimeError(
                    f"Unsupported Agent Lab database schema {version}; expected {SCHEMA_VERSION}."
                )
            if version == 0:
                existing_object = connection.execute(
                    """SELECT type, name FROM sqlite_master
                       WHERE name NOT GLOB 'sqlite_*' LIMIT 1"""
                ).fetchone()
                if existing_object is not None:
                    raise RuntimeError(
                        "Refusing to initialize a nonempty unversioned SQLite database."
                    )
                connection.executescript(_SCHEMA)
                connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._seed_catalog(connection)

    def _seed_catalog(
        self, connection: sqlite3.Connection, entries: Sequence[SeedResource] = BUILTIN_CATALOG
    ) -> None:
        now = utc_now()
        for entry in entries:
            definition = entry.definition
            existing = connection.execute(
                "SELECT kind FROM catalog_definitions WHERE id = ?", (definition.id,)
            ).fetchone()
            if existing is not None and existing["kind"] != definition.kind.value:
                raise CatalogIntegrityError(
                    f"Catalog identity {definition.id!r} changed kind; refusing to rewrite it."
                )
            if existing is None:
                connection.execute(
                    """INSERT INTO catalog_definitions
                       (id, kind, name, summary, created_at) VALUES (?, ?, ?, ?, ?)""",
                    (definition.id, definition.kind.value, definition.name, definition.summary, now),
                )
            else:
                connection.execute(
                    "UPDATE catalog_definitions SET name = ?, summary = ? WHERE id = ?",
                    (definition.name, definition.summary, definition.id),
                )
            for seeded in entry.versions:
                metadata_json = json.dumps(
                    seeded.metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":")
                )
                digest = _version_digest(
                    definition.id, seeded.version, seeded.body, seeded.metadata
                )
                previous = connection.execute(
                    """SELECT body, metadata_json, digest FROM catalog_versions
                       WHERE resource_id = ? AND version = ?""",
                    (definition.id, seeded.version),
                ).fetchone()
                if previous is not None:
                    if (
                        previous["body"] != seeded.body
                        or previous["metadata_json"] != metadata_json
                        or previous["digest"] != digest
                    ):
                        raise CatalogIntegrityError(
                            f"Catalog version {definition.id}@{seeded.version} conflicts "
                            "with its persisted immutable content."
                        )
                    continue
                connection.execute(
                    """INSERT INTO catalog_versions
                       (resource_id, version, body, metadata_json, digest, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (definition.id, seeded.version, seeded.body, metadata_json, digest, now),
                )

    def list_resources(
        self, kind: ResourceKind | None = None, query: str = ""
    ) -> tuple[CatalogResource, ...]:
        with self._connect() as connection:
            sql = "SELECT * FROM catalog_definitions"
            parameters: list[str] = []
            if kind is not None:
                sql += " WHERE kind = ?"
                parameters.append(kind.value)
            sql += " ORDER BY name COLLATE NOCASE, id"
            rows = connection.execute(sql, parameters).fetchall()
            result: list[CatalogResource] = []
            needle = query.strip().casefold()
            for row in rows:
                definition = self._definition(row)
                resource = self._catalog_resource(connection, definition)
                searchable = " ".join(
                    (
                        definition.id,
                        definition.name,
                        definition.summary,
                        *(version.body for version in resource.versions),
                        *(
                            f"{key} {value}"
                            for version in resource.versions
                            for key, value in version.metadata.items()
                        ),
                    )
                ).casefold()
                if needle and needle not in searchable:
                    continue
                result.append(resource)
            return tuple(result)

    def get_resource(self, resource_id: str) -> CatalogResource | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM catalog_definitions WHERE id = ?", (resource_id,)
            ).fetchone()
            if row is None:
                return None
            return self._catalog_resource(connection, self._definition(row))

    def _catalog_resource(
        self, connection: sqlite3.Connection, definition: ResourceDefinition
    ) -> CatalogResource:
        rows = connection.execute(
            """SELECT resource_id, version, body, metadata_json, digest
               FROM catalog_versions WHERE resource_id = ? ORDER BY created_at, version""",
            (definition.id,),
        ).fetchall()
        versions_list: list[ResourceVersion] = []
        for row in rows:
            metadata = json.loads(row["metadata_json"])
            expected_digest = _version_digest(
                row["resource_id"], row["version"], row["body"], metadata
            )
            if expected_digest != row["digest"]:
                raise PersistenceIntegrityError(
                    f"Catalog version {row['resource_id']}@{row['version']} "
                    "failed digest verification."
                )
            versions_list.append(
                ResourceVersion(
                    resource_id=row["resource_id"],
                    version=row["version"],
                    body=row["body"],
                    metadata=metadata,
                    digest=row["digest"],
                )
            )
        return CatalogResource(definition=definition, versions=tuple(versions_list))

    @staticmethod
    def _definition(row: sqlite3.Row) -> ResourceDefinition:
        return ResourceDefinition(
            id=row["id"],
            kind=row["kind"],
            name=row["name"],
            summary=row["summary"],
        )

    def save_composition(
        self,
        *,
        name: str,
        description: str,
        instructions: str,
        bindings: Sequence[tuple[str, int, str, str]],
        model_settings: Sequence[ModelSettings] = (),
        composition_id: str | None = None,
        expected_revision: int | None = None,
        _binding_snapshots: Sequence[CompositionBinding] | None = None,
    ) -> SavedComposition:
        """Save one immutable revision, pinning every submitted resource version exactly."""
        if _binding_snapshots is not None and bindings:
            raise ValueError("Binding selections and snapshots cannot be saved together.")
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if composition_id is None:
                if expected_revision is not None:
                    raise ValueError("A new composition cannot have an expected revision.")
                saved_id = str(uuid.uuid4())
                revision_number = 1
                created_at = utc_now()
            else:
                current = connection.execute(
                    "SELECT current_revision, created_at FROM compositions WHERE id = ?",
                    (composition_id,),
                ).fetchone()
                if current is None:
                    raise CompositionNotFoundError(composition_id)
                if expected_revision is None or current["current_revision"] != expected_revision:
                    raise StaleCompositionError(
                        "This composition changed after the form was opened. "
                        "Reload it before saving."
                    )
                saved_id = composition_id
                revision_number = int(current["current_revision"]) + 1
                created_at = current["created_at"]

            resolved = list(_binding_snapshots) if _binding_snapshots is not None else []
            if _binding_snapshots is None:
                for target, ordinal, resource_id, version in bindings:
                    row = connection.execute(
                        """SELECT d.id, d.kind, d.name, v.version, v.digest
                           FROM catalog_definitions AS d
                           JOIN catalog_versions AS v ON v.resource_id = d.id
                           WHERE d.id = ? AND v.version = ?""",
                        (resource_id, version),
                    ).fetchone()
                    if row is None:
                        raise MissingBindingError(
                            f"Catalog version {resource_id}@{version} does not exist. "
                            "Choose an available version explicitly; no newer version was substituted."
                        )
                    resolved.append(
                        CompositionBinding(
                            target=target,
                            ordinal=ordinal,
                            resource_id=row["id"],
                            version=row["version"],
                            digest=row["digest"],
                            name=row["name"],
                            kind=row["kind"],
                        )
                    )

            draft = CompositionDraft(
                name=name,
                description=description,
                instructions=instructions,
                bindings=tuple(resolved),
                model_settings=tuple(model_settings),
            )
            created = utc_now()
            fingerprint = _composition_digest(
                name=draft.name,
                description=draft.description,
                instructions=draft.instructions,
                bindings=draft.bindings,
                model_settings=draft.model_settings,
            )
            if composition_id is None:
                connection.execute(
                    """INSERT INTO compositions (id, current_revision, created_at, updated_at)
                       VALUES (?, ?, ?, ?)""",
                    (saved_id, revision_number, created_at, created),
                )
            connection.execute(
                """INSERT INTO composition_revisions
                   (composition_id, revision, schema_version, name, description,
                    instructions, content_hash, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    saved_id,
                    revision_number,
                    1,
                    draft.name,
                    draft.description,
                    draft.instructions,
                    fingerprint,
                    created,
                ),
            )
            connection.executemany(
                """INSERT INTO composition_bindings
                   (composition_id, revision, binding_target, binding_ordinal,
                    resource_id, resource_version,
                    resource_name, resource_kind, version_digest)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        saved_id,
                        revision_number,
                        item.target,
                        item.ordinal,
                        item.resource_id,
                        item.version,
                        item.name,
                        item.kind.value,
                        item.digest,
                    )
                    for item in draft.bindings
                ],
            )
            connection.executemany(
                """INSERT INTO composition_models
                   (composition_id, revision, slot, provider, model, parameters_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [
                    (
                        saved_id,
                        revision_number,
                        item.slot,
                        item.provider,
                        item.model,
                        json.dumps(
                            item.parameters,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                    )
                    for item in draft.model_settings
                ],
            )
            if composition_id is not None:
                connection.execute(
                    """UPDATE compositions SET current_revision = ?, updated_at = ? WHERE id = ?""",
                    (revision_number, created, saved_id),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        result = self.get_composition(saved_id)
        if result is None:
            raise RuntimeError("Saved composition disappeared after commit.")
        return result

    def duplicate_composition(
        self,
        composition_id: str,
        *,
        revision: int | None = None,
        name: str | None = None,
    ) -> SavedComposition:
        """Create a new composition identity from an exact saved revision."""
        existing = self.get_composition(composition_id)
        if existing is None:
            raise CompositionNotFoundError(composition_id)
        source = existing.revision
        if revision is not None:
            historical = next(
                (item for item in existing.history if item.revision == revision), None
            )
            if historical is None:
                raise CompositionNotFoundError(f"{composition_id}@{revision}")
            source = historical
        copy_name = name if name is not None else f"{source.name} (copy)"[:120]
        return self.save_composition(
            name=copy_name,
            description=source.description,
            instructions=source.instructions,
            bindings=(),
            model_settings=source.model_settings,
            _binding_snapshots=source.bindings,
        )

    def get_composition_revision(
        self, composition_id: str, revision: int
    ) -> CompositionRevision | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT * FROM composition_revisions
                   WHERE composition_id = ? AND revision = ?""",
                (composition_id, revision),
            ).fetchone()
            if row is None:
                return None
            return self._composition_revision(connection, row)

    def list_compositions(self) -> tuple[SavedComposition, ...]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id FROM compositions ORDER BY updated_at DESC, id"
            ).fetchall()
        compositions = (self.get_composition(row["id"]) for row in rows)
        return tuple(item for item in compositions if item is not None)

    def get_composition(self, composition_id: str) -> SavedComposition | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM compositions WHERE id = ?", (composition_id,)
            ).fetchone()
            if row is None:
                return None
            revision_rows = connection.execute(
                """SELECT * FROM composition_revisions WHERE composition_id = ?
                   ORDER BY revision DESC""",
                (composition_id,),
            ).fetchall()
            history = tuple(
                self._composition_revision(connection, revision_row)
                for revision_row in revision_rows
            )
            current = next(item for item in history if item.revision == row["current_revision"])
            return SavedComposition(
                id=row["id"],
                current_revision=row["current_revision"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                revision=current,
                history=history,
            )

    def _composition_revision(
        self, connection: sqlite3.Connection, row: sqlite3.Row
    ) -> CompositionRevision:
        binding_rows = connection.execute(
            """SELECT b.binding_target, b.binding_ordinal, b.resource_id,
                      b.resource_version, b.resource_name,
                      b.resource_kind, b.version_digest, v.digest AS actual_digest
               FROM composition_bindings AS b
               JOIN catalog_versions AS v
                 ON v.resource_id = b.resource_id AND v.version = b.resource_version
               WHERE b.composition_id = ? AND b.revision = ?
               ORDER BY b.binding_target, b.binding_ordinal""",
            (row["composition_id"], row["revision"]),
        ).fetchall()
        if any(item["version_digest"] != item["actual_digest"] for item in binding_rows):
            raise PersistenceIntegrityError(
                f"Composition {row['composition_id']} revision {row['revision']} "
                "references a catalog version with a mismatched digest."
            )
        bindings = tuple(
            CompositionBinding(
                target=item["binding_target"],
                ordinal=item["binding_ordinal"],
                resource_id=item["resource_id"],
                version=item["resource_version"],
                digest=item["version_digest"],
                name=item["resource_name"],
                kind=item["resource_kind"],
            )
            for item in binding_rows
        )
        model_rows = connection.execute(
            """SELECT slot, provider, model, parameters_json FROM composition_models
               WHERE composition_id = ? AND revision = ? ORDER BY slot""",
            (row["composition_id"], row["revision"]),
        ).fetchall()
        model_settings = tuple(
            ModelSettings(
                slot=item["slot"],
                provider=item["provider"],
                model=item["model"],
                parameters=json.loads(item["parameters_json"]),
            )
            for item in model_rows
        )
        expected_hash = _composition_digest(
            name=row["name"],
            description=row["description"],
            instructions=row["instructions"],
            bindings=bindings,
            model_settings=model_settings,
        )
        if expected_hash != row["content_hash"]:
            raise PersistenceIntegrityError(
                f"Composition {row['composition_id']} revision {row['revision']} "
                "failed digest verification."
            )
        return CompositionRevision(
            composition_id=row["composition_id"],
            revision=row["revision"],
            schema_version=row["schema_version"],
            name=row["name"],
            description=row["description"],
            instructions=row["instructions"],
            content_hash=row["content_hash"],
            created_at=row["created_at"],
            bindings=bindings,
            model_settings=model_settings,
        )
