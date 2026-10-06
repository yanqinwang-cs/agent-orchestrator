"""Minimal JSON API for public discovery and a local private composition workspace."""

from __future__ import annotations

import ipaddress
import json
from collections.abc import Callable
from http import HTTPStatus
from typing import Any
from urllib.parse import parse_qs, urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agent_lab.domain import (
    BindingOrdinal,
    CompositionNotFoundError,
    MAX_PERSISTED_INTEGER,
    MissingBindingError,
    ModelSettings,
    ResourceId,
    ResourceKind,
    RevisionNumber,
    SavedComposition,
    StaleCompositionError,
    Version,
)
from agent_lab.persistence import PersistenceIntegrityError, SQLiteStore


class ApiContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class BindingSelection(ApiContract):
    target: str | None = Field(default=None, min_length=1, max_length=80)
    ordinal: BindingOrdinal
    resource_id: ResourceId
    version: Version


class CompositionSaveRequest(ApiContract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    instructions: str = Field(default="", max_length=20_000)
    bindings: tuple[BindingSelection, ...] = Field(min_length=1, max_length=40)
    model_settings: tuple[ModelSettings, ...] = Field(default=(), max_length=20)


class RevisionSaveRequest(CompositionSaveRequest):
    expected_revision: RevisionNumber


class DuplicateRequest(ApiContract):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    revision: RevisionNumber | None = None


class SQLiteApi:
    """WSGI application with JSON-only routes; it has no presentation or account layer."""

    max_request_bytes = 1_000_000

    def __init__(self, store: SQLiteStore) -> None:
        self.store = store

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> list[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        query = parse_qs(str(environ.get("QUERY_STRING", "")), keep_blank_values=True)
        try:
            _require_loopback_host(environ)
            status, payload, headers = self._dispatch(method, path, query, environ)
        except ValidationError as exc:
            status = HTTPStatus.UNPROCESSABLE_ENTITY
            payload = {
                "error": "validation_error",
                "details": [
                    {
                        "path": ".".join(str(part) for part in item["loc"]),
                        "message": item["msg"],
                    }
                    for item in exc.errors(include_url=False)
                ],
            }
            headers = []
        except MissingBindingError as exc:
            status, payload, headers = (
                HTTPStatus.UNPROCESSABLE_ENTITY,
                {"error": "invalid_binding", "message": str(exc)},
                [],
            )
        except CompositionNotFoundError:
            status, payload, headers = (
                HTTPStatus.NOT_FOUND,
                {"error": "not_found", "message": "Saved composition does not exist."},
                [],
            )
        except StaleCompositionError as exc:
            status, payload, headers = (
                HTTPStatus.CONFLICT,
                {"error": "stale_revision", "message": str(exc)},
                [],
            )
        except PersistenceIntegrityError:
            status, payload, headers = (
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": "persistence_integrity_error",
                    "message": "Persisted Agent Lab data failed integrity validation.",
                },
                [],
            )
        except ValueError as exc:
            status, payload, headers = (
                HTTPStatus.BAD_REQUEST,
                {"error": "invalid_request", "message": str(exc)},
                [],
            )
        except _RequestError as exc:
            status, payload, headers = exc.status, {"error": exc.code, "message": exc.message}, []

        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        response_headers = [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
            *headers,
        ]
        start_response(f"{status.value} {status.phrase}", response_headers)
        return [body]

    def _dispatch(
        self,
        method: str,
        path: str,
        query: dict[str, list[str]],
        environ: dict[str, Any],
    ) -> tuple[HTTPStatus, Any, list[tuple[str, str]]]:
        if path == "/api/catalog" and method == "GET":
            raw_kind = _one(query, "kind")
            try:
                kind = ResourceKind(raw_kind) if raw_kind else None
            except ValueError as exc:
                raise _RequestError(
                    HTTPStatus.BAD_REQUEST, "invalid_kind", "Unknown resource kind."
                ) from exc
            resources = self.store.list_resources(kind=kind, query=_one(query, "q") or "")
            return HTTPStatus.OK, [item.model_dump(mode="json") for item in resources], []

        if path.startswith("/api/catalog/") and method == "GET":
            resource_id = path.removeprefix("/api/catalog/")
            resource = self.store.get_resource(resource_id)
            if resource is None:
                return (
                    HTTPStatus.NOT_FOUND,
                    {"error": "not_found", "message": "Catalog resource does not exist."},
                    [],
                )
            return HTTPStatus.OK, resource.model_dump(mode="json"), []

        if path == "/api/compositions" and method == "GET":
            return (
                HTTPStatus.OK,
                [item.model_dump(mode="json") for item in self.store.list_compositions()],
                [],
            )
        if path == "/api/compositions" and method == "POST":
            request = CompositionSaveRequest.model_validate(self._read_json(environ))
            composition = self.store.save_composition(
                name=request.name,
                description=request.description,
                instructions=request.instructions,
                bindings=tuple(
                    (item.target, item.ordinal, item.resource_id, item.version)
                    for item in request.bindings
                ),
                model_settings=request.model_settings,
            )
            return self._composition_response(composition, HTTPStatus.CREATED)
        if path == "/api/compositions":
            raise _RequestError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "method_not_allowed",
                "Use GET to list compositions or POST to create one.",
            )

        if path.startswith("/api/compositions/"):
            return self._composition_route(method, path, environ)
        if path == "/api/catalog" or path.startswith("/api/catalog/"):
            raise _RequestError(
                HTTPStatus.METHOD_NOT_ALLOWED,
                "method_not_allowed",
                "This catalog route is read-only.",
            )
        return HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "Route does not exist."}, []

    def _composition_route(
        self, method: str, path: str, environ: dict[str, Any]
    ) -> tuple[HTTPStatus, Any, list[tuple[str, str]]]:
        parts = path.removeprefix("/api/compositions/").split("/")
        composition_id = parts[0]
        if len(parts) == 1 and method == "GET":
            composition = self.store.get_composition(composition_id)
            if composition is None:
                raise CompositionNotFoundError(composition_id)
            return HTTPStatus.OK, composition.model_dump(mode="json"), []
        if len(parts) == 2 and parts[1] == "revisions" and method == "POST":
            revision_request = RevisionSaveRequest.model_validate(self._read_json(environ))
            composition = self.store.save_composition(
                name=revision_request.name,
                description=revision_request.description,
                instructions=revision_request.instructions,
                bindings=tuple(
                    (item.target, item.ordinal, item.resource_id, item.version)
                    for item in revision_request.bindings
                ),
                model_settings=revision_request.model_settings,
                composition_id=composition_id,
                expected_revision=revision_request.expected_revision,
            )
            return self._composition_response(composition, HTTPStatus.CREATED)
        if len(parts) == 3 and parts[1] == "revisions" and method == "GET":
            try:
                revision_number = int(parts[2])
            except ValueError as exc:
                raise _RequestError(
                    HTTPStatus.BAD_REQUEST, "invalid_revision", "Revision must be an integer."
                ) from exc
            if revision_number < 1 or revision_number > MAX_PERSISTED_INTEGER:
                raise _RequestError(
                    HTTPStatus.BAD_REQUEST,
                    "invalid_revision",
                    "Revision must fit SQLite's positive integer range.",
                )
            revision = self.store.get_composition_revision(composition_id, revision_number)
            if revision is None:
                return (
                    HTTPStatus.NOT_FOUND,
                    {"error": "not_found", "message": "Composition revision does not exist."},
                    [],
                )
            return HTTPStatus.OK, revision.model_dump(mode="json"), []
        if len(parts) == 2 and parts[1] == "duplicates" and method == "POST":
            duplicate_request = DuplicateRequest.model_validate(self._read_json(environ))
            composition = self.store.duplicate_composition(
                composition_id,
                revision=duplicate_request.revision,
                name=duplicate_request.name,
            )
            return self._composition_response(composition, HTTPStatus.CREATED)
        raise _RequestError(
            HTTPStatus.METHOD_NOT_ALLOWED,
            "method_not_allowed",
            "Method or composition route is unsupported.",
        )

    @staticmethod
    def _composition_response(
        composition: SavedComposition, status: HTTPStatus
    ) -> tuple[HTTPStatus, Any, list[tuple[str, str]]]:
        return (
            status,
            composition.model_dump(mode="json"),
            [("Location", f"/api/compositions/{composition.id}")],
        )

    def _read_json(self, environ: dict[str, Any]) -> Any:
        content_type = str(environ.get("CONTENT_TYPE", "")).split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            raise _RequestError(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                "unsupported_media_type",
                "Request body must use application/json.",
            )
        try:
            size = int(environ.get("CONTENT_LENGTH", "0"))
        except (TypeError, ValueError) as exc:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "invalid_length", "Invalid content length."
            ) from exc
        if size < 0 or size > self.max_request_bytes:
            raise _RequestError(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body_too_large", "Request body is too large."
            )
        stream = environ.get("wsgi.input")
        raw = stream.read(size) if stream is not None else b""
        if len(raw) != size:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "truncated_body", "Request body was incomplete."
            )
        try:
            return json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise _RequestError(
                HTTPStatus.BAD_REQUEST, "invalid_json", "Request body is not valid JSON."
            ) from exc


def _one(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    if not values:
        return None
    if len(values) != 1:
        raise _RequestError(
            HTTPStatus.BAD_REQUEST, "duplicate_query", f"Query parameter {key!r} must occur once."
        )
    return values[0]


def _require_loopback_host(environ: dict[str, Any]) -> None:
    raw_host = environ.get("HTTP_HOST")
    parsed = None
    try:
        parsed = urlsplit(f"//{raw_host}") if isinstance(raw_host, str) else None
        hostname = parsed.hostname if parsed is not None else None
        port = parsed.port if parsed is not None else None
    except ValueError:
        hostname = None
        port = None
    valid_syntax = (
        parsed is not None
        and bool(raw_host)
        and parsed.username is None
        and parsed.password is None
        and not parsed.path
        and not parsed.query
        and not parsed.fragment
        and (port is None or 1 <= port <= 65535)
    )
    loopback = False
    if valid_syntax and hostname is not None:
        normalized = hostname.casefold()
        if normalized == "localhost":
            loopback = True
        else:
            try:
                loopback = ipaddress.ip_address(normalized).is_loopback
            except ValueError:
                pass
    if not loopback:
        raise _RequestError(
            HTTPStatus.FORBIDDEN,
            "invalid_host",
            "The Host header must identify a loopback address.",
        )


class _RequestError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
