# Development

[AGENTS.md](../AGENTS.md) governs the project. This document describes how to validate the surviving implementation.

## Offline baseline

Use Python 3.12+ and the committed `uv.lock`. The full source gate includes the
optional harness extra; omit it only for baseline-only installs:


```sh
uv sync --locked --extra harness --group dev
uv run pytest -m 'not live'
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv lock --check
uv run agent-orchestrator --help
uv run agent-orchestrator --version
```

The default CLI reports that run commands and the UI are unavailable. Its old milestone wording is an implementation cleanup item, not a current roadmap. The offline suite uses local fixtures, fake workers, and local process-owner probes; it makes no live provider calls.

## Separate offline harness

The optional `harness` extra adds the pinned Deep Agents/LangGraph stack without
changing the legacy or creation runtime. Install it explicitly for its integration
gate; an extra-free integration skip is not proof. See [harness architecture and
limits](OFFLINE_HARNESS.md).

```sh
uv sync --locked --extra harness --group dev
uv run --locked --extra harness pytest -q tests/test_harness_records.py tests/test_harness_offline.py
uv run --locked --extra harness python -m agent_harness.demo
uv run --locked --extra harness mypy src
uv lock --check
```

Use the existing offline baseline too when checking shared dependency compatibility.
No new website/composition tests are part of this foundation.

## Agent Lab backend

The backend-only discovery/composition API is independent of the legacy runtime. It uses a file-backed SQLite database and binds only to loopback; do not expose it as a multi-user service. See [backend contracts](DISCOVERY_COMPOSITION_BACKEND.md) for the data model and routes.

```sh
PYTHONPATH=src uv run pytest -q tests/test_agent_lab_store.py tests/test_agent_lab_http_api.py
uv run ruff check src/agent_lab tests/test_agent_lab_store.py tests/test_agent_lab_http_api.py
uv run mypy --follow-imports=normal src/agent_lab
uv run agent-lab-api --help
```

## Configuration and schemas

The legacy loader requires `presets/agents.toml`, all six files under `presets/workflows/`, and `config/{project.example,backends,development}.toml`. Keep these until the loader and dependent tests are migrated together. They do not prescribe Agent Lab's future agent roles, workflow shape, or backend bindings.

```sh
uv run agent-orchestrator validate-config config/project.example.toml
uv run agent-orchestrator validate-config config/backends.toml
uv run agent-orchestrator validate-config config/development.toml
uv run agent-orchestrator validate-config presets/agents.toml
uv run agent-orchestrator validate-config presets/workflows/review.toml
uv run python scripts/check_starter.py
```

The schema regression in `tests/test_cli_and_schemas.py` generates schemas in a temporary directory and compares them with committed bytes. For an authorized contract change, `uv run python scripts/export_schemas.py` regenerates the committed schemas.

`config/project.example.toml` has a placeholder project path and an empty model catalog. Successful configuration validation does not establish readiness for live execution. The build metadata and locked Codex dependency still belong to the previous implementation.

## Optional local tooling

`.codex/config.toml` contains local development execution defaults. Installed skills and `.codex/rules/` are local tooling, not additional project-continuity documents. A local allow rule does not authorize pushing; `AGENTS.md` requires the user's authorization.

`config/development.toml` and `scripts/codex_task.py` provide an optional development launcher. Its presets describe generic implementation, architecture, debugging, review, testing, and research tasks. The launcher applies its own execution settings; those are separate from application backend settings and from the current chat's permissions. Inspect an invocation before using it:

```sh
python3 scripts/codex_task.py review --task 'Review the specified diff against AGENTS.md.' --dry-run
```

No skill installation or external plugin is required for the offline baseline.

## Live Codex boundary

The retained adapter pins `openai-codex==0.159.2` and checks runtime/configuration evidence before admitting read-only report execution. `ORCHESTRATOR_CODEX_HOME` selects a dedicated Codex home. `tests/test_codex_backend_live.py` additionally requires `ORCHESTRATOR_CODEX_LIVE=1`, a concrete `ORCHESTRATOR_CODEX_LIVE_MODEL`, and an optional `ORCHESTRATOR_CODEX_LIVE_EFFORT` (default `high`). The live tests reject the default user Codex home.

These are explicit live settings, not an automatically loaded `.env` configuration. Obtain authorization before live provider calls. Offline tests and previous receipts do not prove current sign-in, model availability, or settlement of detached descendants and remote effects.

## Delivery

Run relevant checks and inspect the final diff and Git status. Preserve unrelated local work. Commit only intended passing changes; push only with user authorization. Keep implementation types in adapters and record validation limits without turning a successful offline check into a hosted-execution claim.
