from __future__ import annotations

import sqlite3

import pytest
from pydantic import ValidationError

from agent_lab.domain import (
    MissingBindingError,
    ModelSettings,
    ResourceKind,
    StaleCompositionError,
)
from agent_lab.persistence import PersistenceIntegrityError, SQLiteStore


def make_store(tmp_path, name: str = "agent-lab.sqlite3") -> SQLiteStore:
    return SQLiteStore(tmp_path / name)


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
        bindings=(("skill/review-checklist", "1.0.0"),),
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
        bindings=(("skill/review-checklist", "1.1.0"),),
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
        bindings=(("prompt/clarify-task", "1.0.0"),),
        model_settings=(ModelSettings(slot="main", provider="provider-a", model="model-a"),),
    )
    store.save_composition(
        composition_id=first.id,
        expected_revision=1,
        name="Research agent",
        description="Changed later",
        instructions="Use a different instruction set.",
        bindings=(("skill/review-checklist", "1.1.0"),),
    )

    duplicate = store.duplicate_composition(first.id, revision=1, name="Evidence variant")
    assert duplicate.id != first.id
    assert duplicate.current_revision == 1
    assert duplicate.revision.name == "Evidence variant"
    assert duplicate.revision.description == "A baseline"
    assert duplicate.revision.bindings == first.revision.bindings
    assert duplicate.revision.model_settings == first.revision.model_settings


def test_missing_and_duplicate_bindings_fail_without_persisting(tmp_path) -> None:
    store = make_store(tmp_path)
    with pytest.raises(MissingBindingError, match="no newer version was substituted"):
        store.save_composition(
            name="Invalid",
            description="",
            instructions="",
            bindings=(("skill/review-checklist", "9.9.9"),),
        )
    assert store.list_compositions() == ()

    with pytest.raises(ValidationError, match="resource can be bound only once"):
        store.save_composition(
            name="Duplicate resource",
            description="",
            instructions="",
            bindings=(
                ("skill/review-checklist", "1.0.0"),
                ("skill/review-checklist", "1.1.0"),
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
        bindings=(("prompt/clarify-task", "1.0.0"),),
    )
    second = store.save_composition(
        composition_id=first.id,
        expected_revision=1,
        name="Agent",
        description="second revision",
        instructions="",
        bindings=(("prompt/clarify-task", "1.0.0"),),
    )
    with pytest.raises(StaleCompositionError):
        store.save_composition(
            composition_id=first.id,
            expected_revision=1,
            name="Agent",
            description="stale revision",
            instructions="",
            bindings=(("prompt/clarify-task", "1.0.0"),),
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
        bindings=(("prompt/clarify-task", "1.0.0"),),
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
        bindings=(("prompt/clarify-task", "1.0.0"),),
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


def test_database_records_a_schema_version(tmp_path) -> None:
    database = tmp_path / "agent-lab.sqlite3"
    SQLiteStore(database)
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 1
