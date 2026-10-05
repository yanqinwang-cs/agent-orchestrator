from __future__ import annotations

import sqlite3
from stat import S_IMODE

import pytest
from pydantic import ValidationError

from agent_lab.domain import (
    MissingBindingError,
    ModelSettings,
    ResourceKind,
    StaleCompositionError,
)
from agent_lab.persistence import CatalogIntegrityError, PersistenceIntegrityError, SQLiteStore


def make_store(tmp_path, name: str = "agent-lab.sqlite3") -> SQLiteStore:
    return SQLiteStore(tmp_path / name)


def binding(
    resource_id: str,
    version: str,
    *,
    target: str = "main",
    ordinal: int = 0,
) -> tuple[str, int, str, str]:
    return target, ordinal, resource_id, version


def test_catalog_search_filters_categories_and_exposes_exact_versions(tmp_path) -> None:
    store = make_store(tmp_path)

    all_resources = store.list_resources()
    assert {resource.definition.kind for resource in all_resources} == set(ResourceKind)
    assert len(store.list_resources(kind=ResourceKind.PLUGIN)) == 1
    matches = store.list_resources(query="boundary conditions")
    assert [resource.definition.id for resource in matches] == ["skill/review-checklist"]

    resource = store.get_resource("skill/review-checklist")
    assert resource is not None
    assert [version.version for version in resource.versions] == ["1.0.0", "1.1.0"]
    assert resource.versions[0].digest != resource.versions[1].digest


def test_composition_save_load_and_edit_pin_exact_catalog_version(tmp_path) -> None:
    store = make_store(tmp_path)
    original = store.save_composition(
        name="Review setup",
        description="First saved variant",
        instructions="Keep findings actionable.",
        bindings=(binding("skill/review-checklist", "1.0.0"),),
        model_settings=(
            ModelSettings(
                slot="reviewer",
                provider="example-provider",
                model="model-snapshot-2026-01",
                parameters={"temperature": 0, "max_tokens": 512},
            ),
        ),
    )
    assert original.current_revision == 1
    assert original.revision.bindings[0].version == "1.0.0"
    assert original.revision.model_settings[0].parameters["temperature"] == 0
    assert len(original.revision.content_hash) == 64

    store = SQLiteStore(tmp_path / "agent-lab.sqlite3")
    loaded = store.get_composition(original.id)
    assert loaded is not None
    assert loaded.revision.content_hash == original.revision.content_hash
    assert loaded.revision.bindings[0].digest == original.revision.bindings[0].digest

    changed = store.save_composition(
        composition_id=original.id,
        expected_revision=1,
        name="Review setup",
        description="Updated variant",
        instructions="Report confirmed defects first.",
        bindings=(binding("skill/review-checklist", "1.1.0"),),
        model_settings=original.revision.model_settings,
    )
    assert changed.current_revision == 2
    assert changed.revision.bindings[0].version == "1.1.0"
    assert changed.history[1].bindings[0].version == "1.0.0"
    assert changed.history[1].content_hash == original.revision.content_hash
    assert store.get_composition_revision(original.id, 1) == original.revision


def test_duplicate_variant_copies_an_exact_historical_revision(tmp_path) -> None:
    store = make_store(tmp_path)
    first = store.save_composition(
        name="Research agent",
        description="A baseline",
        instructions="Cite evidence.",
        bindings=(binding("prompt/clarify-task", "1.0.0"),),
        model_settings=(ModelSettings(slot="main", provider="provider-a", model="model-a"),),
    )
    store.save_composition(
        composition_id=first.id,
        expected_revision=1,
        name="Research agent",
        description="Changed later",
        instructions="Use a different instruction set.",
        bindings=(binding("skill/review-checklist", "1.1.0"),),
    )

    duplicate = store.duplicate_composition(first.id, revision=1, name="Evidence variant")
    assert duplicate.id != first.id
    assert duplicate.current_revision == 1
    assert duplicate.revision.name == "Evidence variant"
    assert duplicate.revision.description == "A baseline"
    assert duplicate.revision.bindings == first.revision.bindings
    assert duplicate.revision.model_settings == first.revision.model_settings


def test_missing_bindings_and_duplicate_target_ordinals_fail_without_persisting(tmp_path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(MissingBindingError, match="no newer version was substituted"):
        store.save_composition(
            name="Invalid",
            description="",
            instructions="",
            bindings=(binding("skill/review-checklist", "9.9.9"),),
        )
    assert store.list_compositions() == ()

    with pytest.raises(ValidationError, match="ordinals must be unique"):
        store.save_composition(
            name="Duplicate resource",
            description="",
            instructions="",
            bindings=(
                binding("skill/review-checklist", "1.0.0"),
                binding("skill/review-checklist", "1.1.0"),
            ),
        )
    with pytest.raises(ValidationError, match="at least 1 item"):
        store.save_composition(
            name="Empty",
            description="",
            instructions="",
            bindings=(),
        )
    assert store.list_compositions() == ()


def test_stale_revision_cannot_overwrite_newer_save(tmp_path) -> None:
    store = make_store(tmp_path)
    first = store.save_composition(
        name="Agent",
        description="",
        instructions="",
        bindings=(binding("prompt/clarify-task", "1.0.0"),),
    )
    second = store.save_composition(
        composition_id=first.id,
        expected_revision=1,
        name="Agent",
        description="second revision",
        instructions="",
        bindings=(binding("prompt/clarify-task", "1.0.0"),),
    )
    with pytest.raises(StaleCompositionError):
        store.save_composition(
            composition_id=first.id,
            expected_revision=1,
            name="Agent",
            description="stale revision",
            instructions="",
            bindings=(binding("prompt/clarify-task", "1.0.0"),),
        )
    assert store.get_composition(first.id).current_revision == second.current_revision


def test_model_settings_reject_credentials_and_allow_nonsecret_parameters(tmp_path) -> None:
    with pytest.raises(ValidationError, match="cannot contain credentials"):
        ModelSettings(
            slot="main",
            provider="provider-a",
            model="model-a",
            parameters={"api_key": "not-allowed"},
        )
    with pytest.raises(ValidationError, match="credentials or secret fields"):
        ModelSettings(
            slot="main",
            provider="provider-a",
            model="model-a",
            parameters={"refresh_token": "not-allowed"},
        )
    with pytest.raises(ValidationError, match="finite number"):
        ModelSettings(
            slot="main",
            provider="provider-a",
            model="model-a",
            parameters={"temperature": float("nan")},
        )

    store = make_store(tmp_path)
    saved = store.save_composition(
        name="Configured agent",
        description="",
        instructions="",
        bindings=(binding("prompt/clarify-task", "1.0.0"),),
        model_settings=(
            ModelSettings(
                slot="main",
                provider="provider-a",
                model="snapshot-id",
                parameters={"temperature": 0.2, "max_tokens": 800},
            ),
        ),
    )
    assert saved.revision.model_settings[0].model == "snapshot-id"


def test_immutable_catalog_versions_and_read_digest_verification(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    store = SQLiteStore(database)
    with sqlite3.connect(database) as connection:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            connection.execute(
                "UPDATE catalog_versions SET body = 'changed' WHERE resource_id = ?",
                ("skill/review-checklist",),
            )
        connection.execute("DROP TRIGGER catalog_versions_no_update")
        connection.execute(
            "UPDATE catalog_versions SET body = 'tampered' WHERE resource_id = ? AND version = ?",
            ("skill/review-checklist", "1.0.0"),
        )

    with pytest.raises(PersistenceIntegrityError, match="digest verification"):
        store.get_resource("skill/review-checklist")


def test_saved_binding_keeps_its_display_snapshot_when_definition_changes(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    store = SQLiteStore(database)
    saved = store.save_composition(
        name="Pinned catalog binding",
        description="",
        instructions="",
        bindings=(binding("prompt/clarify-task", "1.0.0"),),
    )
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE catalog_definitions SET name = ? WHERE id = ?",
            ("Renamed later", "prompt/clarify-task"),
        )

    loaded = store.get_composition(saved.id)
    assert loaded.revision.bindings[0].name == "Clarify a task"
    assert loaded.revision.bindings[0].kind == ResourceKind.PROMPT
    assert store.get_resource("prompt/clarify-task").definition.name == "Renamed later"

    duplicate = store.duplicate_composition(saved.id, name=saved.revision.name)
    assert duplicate.revision.bindings == saved.revision.bindings
    assert duplicate.revision.content_hash == saved.revision.content_hash


def test_database_records_a_schema_version(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    SQLiteStore(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 2


def test_schema_v1_database_is_rejected_without_modification(tmp_path) -> None:
    database = tmp_path / "agent-lab-v1.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE preserved_data (value TEXT NOT NULL)")
        connection.execute("INSERT INTO preserved_data VALUES ('keep me')")
        connection.execute("PRAGMA user_version = 1")

    with pytest.raises(RuntimeError, match="schema 1; expected 2"):
        SQLiteStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
        assert connection.execute("SELECT value FROM preserved_data").fetchone()[0] == "keep me"


def test_nonempty_unversioned_database_is_rejected_without_modification(tmp_path) -> None:
    database = tmp_path / "unrelated.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE unrelated_data (value TEXT NOT NULL)")
        connection.execute("INSERT INTO unrelated_data VALUES ('keep me')")

    with pytest.raises(RuntimeError, match="nonempty unversioned"):
        SQLiteStore(database)

    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
        assert connection.execute("SELECT value FROM unrelated_data").fetchone()[0] == "keep me"
        agent_lab_objects = connection.execute(
            """SELECT name FROM sqlite_master
               WHERE name IN ('catalog_definitions', 'compositions')"""
        ).fetchall()
        assert agent_lab_objects == []


def test_binding_targets_and_order_survive_reload_and_resource_reuse(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    store = SQLiteStore(database)
    saved = store.save_composition(
        name="Planner and reviewer",
        description="",
        instructions="",
        bindings=(
            binding("skill/review-checklist", "1.1.0", target="planner", ordinal=1),
            binding("prompt/clarify-task", "1.0.0", target="reviewer", ordinal=0),
            binding("prompt/clarify-task", "1.0.0", target="planner", ordinal=0),
        ),
    )

    reloaded = SQLiteStore(database).get_composition(saved.id)
    assert reloaded is not None
    assert [
        (item.target, item.ordinal, item.resource_id) for item in reloaded.revision.bindings
    ] == [
        ("planner", 0, "prompt/clarify-task"),
        ("planner", 1, "skill/review-checklist"),
        ("reviewer", 0, "prompt/clarify-task"),
    ]
    assert reloaded.revision.content_hash == saved.revision.content_hash


def test_reopening_catalog_refreshes_display_metadata_but_rejects_kind_drift(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    SQLiteStore(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE catalog_definitions SET name = ?, summary = ? WHERE id = ?",
            ("Stale name", "Stale summary", "prompt/clarify-task"),
        )

    refreshed = SQLiteStore(database).get_resource("prompt/clarify-task")
    assert refreshed is not None
    assert refreshed.definition.name == "Clarify a task"
    assert refreshed.definition.summary == (
        "A prompt structure for making objectives and acceptance criteria explicit."
    )

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER catalog_definition_identity_no_update")
        connection.execute(
            "UPDATE catalog_definitions SET kind = ? WHERE id = ?",
            ("skill", "prompt/clarify-task"),
        )
    with pytest.raises(CatalogIntegrityError, match="changed kind"):
        SQLiteStore(database)


def test_database_and_rollback_journal_are_owner_only(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    database.touch(mode=0o666)
    database.chmod(0o666)
    SQLiteStore(database)
    assert S_IMODE(database.stat().st_mode) == 0o600

    with sqlite3.connect(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "UPDATE catalog_definitions SET summary = ? WHERE id = ?",
            ("Temporary uncommitted summary", "prompt/clarify-task"),
        )
        journal = database.with_name(f"{database.name}-journal")
        assert journal.exists()
        assert S_IMODE(journal.stat().st_mode) == 0o600
        connection.rollback()
