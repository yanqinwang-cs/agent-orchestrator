# Agent Orchestrator

Agent Orchestrator is a local-first, inspectable harness for running reusable specialist agents through bounded workflows. It combines deterministic execution control, optional semantic decision routing, and pluggable harness-backed or direct-model worker runtimes.

It is a personal open-source developer tool. Success means practical usefulness, user control, inspectability, reproducibility, flexibility and strong engineering quality.

Milestones 1–5 are complete: typed configuration, deterministic run resolution, versioned JSON Schemas, the SQLite ledger, an offline coordinator for all six shipped workflows, runtime controls/recovery, and bounded semantic decision infrastructure. The coordinator and ledger remain authoritative for workflow progression, policy, concurrency, retries, handoffs and persisted state. The provider-neutral `DecisionEngine` returns bounded results; deterministic policy validates them and the coordinator executes any permitted action. Only deterministic and scripted fake inference engines are implemented.

Codex is planned as the first real worker backend because it fits the existing subscription-backed workflow. The current runtime implements only the fake backend; it does not yet launch Codex, create project worktrees or provide a web UI. See the [implementation plan](docs/IMPLEMENTATION_PLAN.md) for target architecture, contracts and the ten-milestone roadmap, and the [integration audit](docs/INTEGRATION_AUDIT.md) for Codex evidence and integration limits.

## Set up and validate

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). SQLite comes with Python. The completed first five milestones need no Node, Codex sign-in or live model access.

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

With no subcommand, the CLI reports that run commands and the UI are not implemented. It does not start a placeholder dashboard. The default test suite uses only local fixtures and fake workers; live provider calls are not a test dependency.

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
| `tasks/01-foundation.md` | Historical milestone 1 task specification |
| `src/orchestrator/` | Versioned models, config validation, pure resolver, bounded execution coordinator, CLI, fake backend, SQLite ledger and artifact store |
| `schemas/` | JSON Schemas generated from the Pydantic models |
| `tests/` | Offline schema, resolver, validation, CLI and fake-backend tests |

The application TOML files are schema-v1 product fixtures. `config/development.toml` remains a separate development preset catalog; it is loaded through its own model and never becomes product agent profiles.

Product `AgentProfile` records currently carry a default backend and model-binding alias. The v1 resolver can vary the model binding and effort within the profile's backend and workflow policy; selecting a different runtime requires the planned versioned execution-binding contract. Repository development presets remain Codex CLI instructions for working on this project and do not define product worker runtimes.

## Durable storage

`SQLiteLedger` owns a versioned SQLite database with foreign keys, WAL mode, full synchronous commits and a configurable busy timeout. One revision-checked transaction writes projections, attributable events, command receipts, reservations and outbox intent together. Resolved run and attempt specifications and project configuration revisions are content-addressed immutable records. Additive migrations preserve worker results and stage outputs (v2), control receipts and attention state (v3), and immutable decision requests with write-once replies/dispositions (v4).

`CoordinatorOwnership` combines an OS file lock with a persisted owner generation. `claim_next_outbox` marks an action claimed before any later dispatcher performs an external effect. A claimed action stays distinguishable from pending after restart and is not blindly selected again; fake-backed reconciliation settles evidenced terminal outcomes and retains unknown ownership for attention. `ArtifactStore` writes and hashes bytes under `runs/<run>/attempts/<attempt>/artifacts/`, atomically renames the completed file, then commits its manifest and event. A crash between rename and the SQLite commit can leave an unreferenced content-addressed file, but cannot publish a manifest for incomplete bytes.

## Bounded fake execution

`ExecutionCoordinator` advances only from the persisted resolved run, stage projections, attempt lineage and durable reservations. It uses stable workflow and slot order, frozen fixed/select-one/elastic selections, the frozen workflow policy, and global/project/run/stage reservations. Attempt specifications, capacity reservations and launch intents commit together. Dispatch claims the outbox action before calling the backend, then records acknowledgement separately. Known classified failures may retry within both workflow and profile limits; unknown launch ownership keeps its reservations and is never replayed automatically.

The scripted `FakeBackend` can hold start acknowledgements and worker events on explicit barriers. Its manual clock supports deterministic timeout tests. The end-to-end suite drives Review, Prototype, Feature, Debug, Research and Final handoff offline, including both Feature branches.

The normalized worker envelope currently contains output names, schema IDs, hashes and a summary, but no report or patch bytes and no registry of stage-specific body schemas. The coordinator checks envelope identity, input/workspace revisions, required output names, hash shape and safe relative paths. It cannot inspect report sections or verify that a summary labels limitations or unresolved claims. Typed payload contracts and content validation are planned before real write workflows.
