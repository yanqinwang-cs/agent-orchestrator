# Discovery and composition backend

This document describes the first backend-only Agent Lab slice. It is separate from the legacy orchestration runtime. It does not define page layout, authentication, a team model, or a visual identity.

## Boundary and operation

The backend uses the repository's Python/Pydantic baseline, SQLite, and the Python standard-library WSGI server. The API is intentionally small and JSON-only. Run it with:

```sh
uv run agent-lab-api --help
uv run agent-lab-api --database ~/.agent-lab/agent-lab.sqlite3 --port 8765
```

The server binds only to `127.0.0.1` and rejects requests whose `Host` header is not `localhost` or a loopback IP address. Composition endpoints are a local single-user workspace, not an authenticated access-control system. Do not expose this server on a network or use it as a multi-user service. It does not implement accounts, teams, invitations, or sharing.

The database path can also be set with `AGENT_LAB_DATABASE`. A file-backed database is required. The database and SQLite sidecar files are forced to owner-read/write permissions, including when a custom path already exists. SQLite `PRAGMA user_version` is `3` for this schema. A version or layout mismatch fails closed without migrating, deleting, or interpreting an unsupported database.

## Persistence contracts

- `catalog_definitions` holds stable resource IDs and kinds plus current names and discovery summaries. Initialization refreshes display metadata for a matching stable identity and rejects kind drift.
- `catalog_versions` holds immutable version labels, content, metadata, and SHA-256 digests. SQLite triggers reject updates and deletes. The digest covers the resource ID, exact version, content, and metadata.
- `compositions` is a stable saved-configuration identity with a current revision pointer.
- `composition_revisions` holds immutable snapshots of composition name, description, instructions, schema version, model settings, and a canonical content hash. Edits append a revision and advance the current pointer in one transaction.
- `composition_bindings` records a global ordinal together with the exact resource ID, version, bound display identity, and digest. Prompt bindings also require one agent target; other resource kinds cannot specify a target. Applying one prompt to two agents is represented by two bindings. Each row has a foreign key to its exact catalog version; a missing version is an error and is never replaced with a newer one.
- `composition_models` stores composition-scoped provider/model identifiers and scalar parameters. Credential-like parameter names are rejected, but parameter values are not scanned for secrets. Callers must not submit credentials or provider SDK objects.

The composition hash is SHA-256 over canonical JSON with sorted keys, bindings ordered by ordinal, model settings, and `schema_version`. Reads recompute catalog and composition digests and fail if immutable bytes no longer match their recorded hashes. Duplication creates a new composition identity from an exact current or historical revision; it does not mutate or alias the source. The provider and model fields are saved exactly as supplied, but a provider may use mutable aliases; this digest identifies the saved configuration, not the provider's future model behavior or availability. Model parameters are limited to scalar JSON values in this slice; credential-like names are blocked as a guardrail, not as secret detection.

The catalog is currently seeded from `agent_lab.catalog.BUILTIN_CATALOG` at initialization. These entries are descriptive examples, not installed tools or runnable agents. There are no experiment, execution, benchmark-run, or result records.

## HTTP API

Base URL: `http://127.0.0.1:8765`. All request and response bodies use JSON. Resource IDs contain `/`, so catalog detail paths retain that segment structure.

| Method and path | Purpose |
| --- | --- |
| `GET /api/catalog?q=...&kind=...` | Search names, summaries, version bodies, and metadata; optionally filter by kind. |
| `GET /api/catalog/{resource_id}` | Read one definition and all exact versions. |
| `GET /api/compositions` | List the local user's saved compositions, current revision first. |
| `POST /api/compositions` | Create a composition at revision 1. |
| `GET /api/compositions/{id}` | Load the current revision and revision history. |
| `POST /api/compositions/{id}/revisions` | Append an edit using a required `expected_revision` concurrency check. |
| `GET /api/compositions/{id}/revisions/{revision}` | Load one exact historical snapshot. |
| `POST /api/compositions/{id}/duplicates` | Create an independent variant from an exact revision. Optional JSON fields: `name`, `revision`. |

Create/revision bodies use `name`, optional `description` and `instructions`, `bindings` as `{ "ordinal", "resource_id", "version" }` entries with a required `target` only for prompts, and optional `model_settings` entries with `slot`, `provider`, `model`, and scalar `parameters`. New compositions require at least one binding. Binding ordinals must be unique within a composition, and model slots must be unique within one composition revision.

Errors are JSON. Invalid input and missing exact bindings return `422`; unknown compositions or revisions return `404`; stale revision saves return `409`; and rejected hosts return `403`. Unsupported content types return `415`, oversized request bodies return `413`, malformed JSON returns `400`, and persisted-data integrity failures return a generic `500` without exposing stored values. The API does not launch or benchmark a saved composition.

## Validation

The focused backend tests are:

```sh
PYTHONPATH=src uv run pytest -q tests/test_agent_lab_store.py tests/test_agent_lab_http_api.py
```

These tests exercise discovery/search, exact version binding, append-only saves, historical loads, duplicated variants, model settings, request validation, concurrency conflicts, and integrity checks. They do not run legacy harness end-to-end tests or any provider/model calls.
