# Agent Orchestrator — Milestone 1 foundation

Milestone 1 supplies a working Python package for typed configuration, static validation, deterministic resolution, JSON Schemas and fake worker contracts. Worker execution, persistence and the web UI are not implemented yet.

**Decision:** a small deterministic Python coordinator, SQLite, the official Python Codex SDK, and a FastAPI/Jinja local UI. The coordinator owns workflow state; Codex owns each worker's model, tools and authentication. No coordinator model is required in v1.

Start with [the implementation plan](docs/IMPLEMENTATION_PLAN.md). It contains the architecture, contracts, state machine, UI, tests and eight milestones. [The integration audit](docs/INTEGRATION_AUDIT.md) records primary sources, version checks and the remaining integration gates.

## Set up and validate

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). SQLite comes with Python. Milestone 1 does not need Git, Node, Codex sign-in, or live model access.

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
| `src/orchestrator/` | Versioned models, config validation, pure resolver, CLI and fake backend |
| `schemas/` | JSON Schemas generated from the Pydantic models |
| `tests/` | Offline schema, resolver, validation, CLI and fake-backend tests |

The application TOML files are schema-v1 product fixtures. `config/development.toml` remains a separate development preset catalog; it is loaded through its own model and never becomes product agent profiles.
