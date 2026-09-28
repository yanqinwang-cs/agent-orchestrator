# Agent Orchestrator — Milestones 1–2 foundation

Milestones 1–2 supply typed configuration, static validation, deterministic run resolution, versioned JSON Schemas, fake worker contracts, and the durable local run ledger. Scheduling, worker execution, live Codex integration and the web UI are not implemented yet.

**Decision:** a small deterministic Python coordinator, SQLite, the official Python Codex SDK, and a FastAPI/Jinja local UI. The coordinator owns workflow state; Codex owns each worker's model, tools and authentication. No coordinator model is required in v1.

Start with [the implementation plan](docs/IMPLEMENTATION_PLAN.md). It contains the architecture, contracts, state machine, UI, tests and eight milestones. [The integration audit](docs/INTEGRATION_AUDIT.md) records primary sources, version checks and the remaining integration gates.

## Set up and validate

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). SQLite comes with Python. The first two milestones do not need Node, Codex sign-in, or live model access.

Install the locked development dependencies and validate the shipped configuration:

```sh
uv sync --locked --group dev
uv run agent-orchestrator validate-config presets/agents.toml
uv run agent-orchestrator validate-config presets/workflows/feature.toml
uv run python scripts/export_schemas.py
```

Current checks:

```sh
uv run pytest -m 'not live'
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run agent-orchestrator --help
uv run agent-orchestrator --version
uv run agent-orchestrator validate-config config/project.example.toml
```

With no subcommand, the CLI reports that execution and the UI are not implemented. It does not start a placeholder dashboard. The default test suite uses only local fixtures and fake workers; live provider calls are not a test dependency.

## Package map

| File | Purpose |
|---|---|
| `AGENTS.md` | Concise implementation instructions |
| `.codex/config.toml` | Development sandbox and approval defaults |
| `.env.example` | Planned app settings; contains no provider credentials |
| `config/development.toml` | Six development execution presets |
| `scripts/codex_task.py` | Portable preset launcher; `--dry-run` shows the exact invocation |
| `config/project.example.toml`, `config/backends.toml` | Proposed typed application settings |
| `presets/agents.toml`, `presets/workflows/*.toml` | Initial product agents and six workflows |
| `docs/IMPLEMENTATION_PLAN.md` | Authoritative product contracts and milestone acceptance |
| `docs/INTEGRATION_AUDIT.md` | Runtime choice, Codex integration and evidence boundaries |
| `docs/DEVELOPMENT.md` | Development presets, skills and dependency policy |
| `tasks/01-foundation.md` | Exact first implementation task |
| `src/orchestrator/` | Versioned models, config validation, pure resolver, CLI, fake backend, SQLite ledger and artifact store |
| `schemas/` | JSON Schemas generated from the Pydantic models |
| `tests/` | Offline schema, resolver, validation, CLI and fake-backend tests |

The application TOML files are schema-v1 product fixtures. `config/development.toml` remains a separate development preset catalog; it is loaded through its own model and never becomes product agent profiles.

## Durable storage

`SQLiteLedger` owns a versioned SQLite database with foreign keys, WAL mode, full synchronous commits and a configurable busy timeout. One revision-checked transaction writes projections, attributable events, command receipts, reservations and outbox intent together. Resolved run and attempt specifications and project configuration revisions are content-addressed immutable records.

`CoordinatorOwnership` combines an OS file lock with a persisted owner generation. `claim_next_outbox` marks an action claimed before any later dispatcher performs an external effect. A claimed action stays distinguishable from pending after restart and is not blindly selected again; reconciliation is a later milestone. `ArtifactStore` writes and hashes bytes under `runs/<run>/attempts/<attempt>/artifacts/`, atomically renames the completed file, then commits its manifest and event. A crash between rename and the SQLite commit can leave an unreferenced content-addressed file, but cannot publish a manifest for incomplete bytes.
