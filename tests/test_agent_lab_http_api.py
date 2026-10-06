from __future__ import annotations

import io
import json
import sqlite3
from typing import Any
from urllib.parse import urlencode
from wsgiref.util import setup_testing_defaults

from agent_lab.http_api import SQLiteApi
from agent_lab.persistence import SQLiteStore


def request(
    application: SQLiteApi,
    method: str,
    path: str,
    *,
    query: dict[str, str] | None = None,
    body: Any = None,
    host: str | None = "127.0.0.1",
) -> tuple[int, dict[str, str], Any]:
    encoded = b"" if body is None else json.dumps(body).encode("utf-8")
    environ: dict[str, Any] = {}
    setup_testing_defaults(environ)
    environ.update(
        REQUEST_METHOD=method,
        PATH_INFO=path,
        QUERY_STRING=urlencode(query or {}),
        CONTENT_TYPE="application/json" if body is not None else "",
        CONTENT_LENGTH=str(len(encoded)),
        **{"wsgi.input": io.BytesIO(encoded)},
    )
    if host is not None:
        environ["HTTP_HOST"] = host
    else:
        environ.pop("HTTP_HOST", None)
    response: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        response["status"] = int(status.split(" ", 1)[0])
        response["headers"] = dict(headers)

    result = b"".join(application(environ, start_response))
    parsed = json.loads(result) if result else None
    return response["status"], response["headers"], parsed


def binding(
    resource_id: str,
    version: str,
    *,
    target: str | None = None,
    ordinal: int = 0,
) -> dict[str, str | int | None]:
    result: dict[str, str | int | None] = {
        "ordinal": ordinal,
        "resource_id": resource_id,
        "version": version,
    }
    if target is not None or resource_id.startswith("prompt/"):
        result["target"] = target if target is not None else "main"
    return result


def test_catalog_api_search_and_detail_use_shared_resource_versions(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    status, _, results = request(api, "GET", "/api/catalog", query={"q": "boundary conditions"})
    assert status == 200
    assert [item["definition"]["id"] for item in results] == ["skill/review-checklist"]
    assert len(results[0]["versions"]) == 2

    status, _, plugin = request(api, "GET", "/api/catalog", query={"kind": "plugin"})
    assert status == 200
    assert plugin[0]["definition"]["kind"] == "plugin"

    status, _, detail = request(api, "GET", "/api/catalog/skill/review-checklist")
    assert status == 200
    assert detail["versions"][1]["version"] == "1.1.0"


def test_api_creates_revises_retrieves_and_duplicates_compositions(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    payload = {
        "name": "Research baseline",
        "description": "First variant",
        "instructions": "Cite source material.",
        "bindings": [
            binding("skill/review-checklist", "1.1.0", ordinal=2),
            binding("prompt/clarify-task", "1.0.0", target="reviewer", ordinal=0),
            binding("prompt/clarify-task", "1.0.0", target="planner", ordinal=1),
        ],
        "model_settings": [
            {
                "slot": "main",
                "provider": "provider-a",
                "model": "model-snapshot-1",
                "parameters": {"temperature": 0, "max_tokens": 400},
            }
        ],
    }
    status, headers, created = request(api, "POST", "/api/compositions", body=payload)
    assert status == 201
    assert headers["Location"] == f"/api/compositions/{created['id']}"
    composition_id = created["id"]
    assert created["revision"]["model_settings"][0]["model"] == "model-snapshot-1"
    assert [
        (item["target"], item["ordinal"], item["resource_id"])
        for item in created["revision"]["bindings"]
    ] == [
        ("reviewer", 0, "prompt/clarify-task"),
        ("planner", 1, "prompt/clarify-task"),
        (None, 2, "skill/review-checklist"),
    ]

    updated_payload = {
        **payload,
        "description": "Second variant",
        "bindings": [binding("skill/review-checklist", "1.1.0")],
        "expected_revision": 1,
    }
    status, _, updated = request(
        api,
        "POST",
        f"/api/compositions/{composition_id}/revisions",
        body=updated_payload,
    )
    assert status == 201
    assert updated["current_revision"] == 2
    assert updated["revision"]["bindings"][0]["version"] == "1.1.0"

    status, _, old_revision = request(api, "GET", f"/api/compositions/{composition_id}/revisions/1")
    assert status == 200
    assert old_revision["bindings"][0]["resource_id"] == "prompt/clarify-task"

    status, _, duplicate = request(
        api,
        "POST",
        f"/api/compositions/{composition_id}/duplicates",
        body={"revision": 1, "name": "Research alternative"},
    )
    assert status == 201
    assert duplicate["id"] != composition_id
    assert duplicate["revision"]["name"] == "Research alternative"
    assert duplicate["revision"]["bindings"][0]["resource_id"] == "prompt/clarify-task"

    status, _, error = request(
        api,
        "POST",
        f"/api/compositions/{composition_id}/duplicates",
        body={"revision": 999},
    )
    assert status == 404
    assert error["error"] == "not_found"

    status, _, listing = request(api, "GET", "/api/compositions")
    assert status == 200
    assert len(listing) == 2


def test_api_rejects_missing_versions_credential_names_and_stale_writes(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    invalid = {
        "name": "Invalid",
        "bindings": [binding("skill/review-checklist", "99.0.0")],
    }
    status, _, error = request(api, "POST", "/api/compositions", body=invalid)
    assert status == 422
    assert error["error"] == "invalid_binding"
    assert "no newer version was substituted" in error["message"]

    secret = {
        "name": "Secret-bearing config",
        "bindings": [binding("prompt/clarify-task", "1.0.0")],
        "model_settings": [
            {
                "slot": "main",
                "provider": "provider-a",
                "model": "model-a",
                "parameters": {"api_key": "never-persist"},
            }
        ],
    }
    status, _, error = request(api, "POST", "/api/compositions", body=secret)
    assert status == 422
    assert error["error"] == "validation_error"
    assert "never-persist" not in json.dumps(error)
    status, _, listing = request(api, "GET", "/api/compositions")
    assert status == 200
    assert listing == []

    valid = {
        "name": "First",
        "bindings": [binding("prompt/clarify-task", "1.0.0")],
        "model_settings": [
            {
                "slot": "main",
                "provider": "provider-a",
                "model": "model-a",
                "parameters": {"note": "sk-example-value-is-not-secret-scanned"},
            }
        ],
    }
    status, _, created = request(api, "POST", "/api/compositions", body=valid)
    assert status == 201
    assert (
        created["revision"]["model_settings"][0]["parameters"]["note"]
        == "sk-example-value-is-not-secret-scanned"
    )
    update = {**valid, "expected_revision": 1}
    status, _, _ = request(
        api,
        "POST",
        f"/api/compositions/{created['id']}/revisions",
        body=update,
    )
    assert status == 201
    status, _, error = request(
        api,
        "POST",
        f"/api/compositions/{created['id']}/revisions",
        body=update,
    )
    assert status == 409
    assert error["error"] == "stale_revision"

    status, _, listing = request(api, "GET", "/api/compositions")
    assert status == 200
    assert listing[0]["current_revision"] == 2


def test_api_enforces_prompt_targets_and_global_binding_order(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))

    status, _, error = request(
        api,
        "POST",
        "/api/compositions",
        body={
            "name": "Targeted skill",
            "bindings": [
                binding("skill/review-checklist", "1.0.0", target="planner")
            ],
        },
    )
    assert status == 422
    assert error["error"] == "validation_error"

    status, _, error = request(
        api,
        "POST",
        "/api/compositions",
        body={
            "name": "Untargeted prompt",
            "bindings": [
                {
                    "ordinal": 0,
                    "resource_id": "prompt/clarify-task",
                    "version": "1.0.0",
                }
            ],
        },
    )
    assert status == 422
    assert error["error"] == "validation_error"


def test_api_rejects_persisted_integers_outside_sqlite_range(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    too_large = 1 << 63

    status, _, error = request(
        api,
        "POST",
        "/api/compositions",
        body={
            "name": "Oversized ordinal",
            "bindings": [
                binding("prompt/clarify-task", "1.0.0", ordinal=too_large)
            ],
        },
    )
    assert status == 422
    assert error["error"] == "validation_error"

    status, _, created = request(
        api,
        "POST",
        "/api/compositions",
        body={"name": "Valid", "bindings": [binding("prompt/clarify-task", "1.0.0")]},
    )
    assert status == 201

    status, _, error = request(
        api,
        "GET",
        f"/api/compositions/{created['id']}/revisions/{too_large}",
    )
    assert status == 400
    assert error["error"] == "invalid_revision"

    status, _, error = request(
        api,
        "POST",
        f"/api/compositions/{created['id']}/duplicates",
        body={"revision": too_large},
    )
    assert status == 422
    assert error["error"] == "validation_error"

    status, _, error = request(
        api,
        "POST",
        f"/api/compositions/{created['id']}/revisions",
        body={
            "name": "Invalid revision",
            "bindings": [binding("prompt/clarify-task", "1.0.0")],
            "expected_revision": too_large,
        },
    )
    assert status == 422
    assert error["error"] == "validation_error"


def test_api_returns_safe_errors_for_invalid_persisted_data(tmp_path) -> None:
    database = tmp_path / "api.sqlite3"
    api = SQLiteApi(SQLiteStore(database))
    status, _, created = request(
        api,
        "POST",
        "/api/compositions",
        body={
            "name": "Stored",
            "bindings": [binding("prompt/clarify-task", "1.0.0")],
            "model_settings": [
                {"slot": "main", "provider": "provider-a", "model": "model-a"}
            ],
        },
    )
    assert status == 201

    with sqlite3.connect(database) as connection:
        connection.execute("DROP TRIGGER catalog_versions_no_update")
        connection.execute(
            "UPDATE catalog_versions SET metadata_json = ? WHERE resource_id = ?",
            ("stored-catalog-secret", "prompt/clarify-task"),
        )
        connection.execute("DROP TRIGGER composition_models_no_update")
        connection.execute(
            "UPDATE composition_models SET parameters_json = ? WHERE composition_id = ?",
            ("stored-model-secret", created["id"]),
        )

    status, _, catalog_error = request(api, "GET", "/api/catalog/prompt/clarify-task")
    assert status == 500
    assert catalog_error == {
        "error": "persistence_integrity_error",
        "message": "Persisted Agent Lab data failed integrity validation.",
    }
    assert "stored-catalog-secret" not in json.dumps(catalog_error)

    status, _, composition_error = request(
        api, "GET", f"/api/compositions/{created['id']}"
    )
    assert status == 500
    assert composition_error == catalog_error
    assert "stored-model-secret" not in json.dumps(composition_error)


def test_api_validates_methods_and_json_request_bodies(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    status, _, error = request(api, "POST", "/api/catalog", body={})
    assert status == 405
    assert error["error"] == "method_not_allowed"

    environ: dict[str, Any] = {}
    setup_testing_defaults(environ)
    environ.update(
        REQUEST_METHOD="POST",
        PATH_INFO="/api/compositions",
        CONTENT_TYPE="text/plain",
        CONTENT_LENGTH="2",
        HTTP_HOST="127.0.0.1",
        **{"wsgi.input": io.BytesIO(b"{}")},
    )
    response: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        response["status"] = int(status.split(" ", 1)[0])

    body = b"".join(api(environ, start_response))
    assert response["status"] == 415
    assert json.loads(body)["error"] == "unsupported_media_type"


def test_api_rejects_non_loopback_or_missing_host_before_dispatch(tmp_path) -> None:
    api = SQLiteApi(SQLiteStore(tmp_path / "api.sqlite3"))
    payload = {
        "name": "Must not persist",
        "bindings": [binding("prompt/clarify-task", "1.0.0")],
    }

    status, _, error = request(
        api,
        "POST",
        "/api/compositions",
        body=payload,
        host="attacker.example",
    )
    assert status == 403
    assert error["error"] == "invalid_host"

    status, _, error = request(api, "GET", "/api/catalog", host=None)
    assert status == 403
    assert error["error"] == "invalid_host"

    status, _, catalog = request(api, "GET", "/api/catalog", host="localhost:8765")
    assert status == 200
    assert catalog

    status, _, compositions = request(api, "GET", "/api/compositions")
    assert status == 200
    assert compositions == []
