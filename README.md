# Agent Lab

Agent Lab is a public venture/research project for defining and evaluating intelligent systems and the interfaces between their components. It aims to support controlled experiments, inspectable results, reproducible reruns, and a future benchmark/discovery surface.

The research direction includes information selection, representation, recipients, retrieval, and execution scheduling. The guiding principle is to use the cheapest representation that preserves the information required for the downstream decision. Strong baselines and negative results matter.

[AGENTS.md](AGENTS.md) is the sole project-level instruction and continuity authority.

## Current implementation

This checkout still contains the previous Agent Orchestrator implementation: typed workflow configuration, immutable snapshots, a SQLite ledger, filesystem artifacts, a deterministic workflow coordinator, fake execution/decision adapters, and a pinned Codex SDK adapter. A separate `agent_lab` backend now provides a curated, versioned discovery catalog, a local single-user composition workspace with immutable saved revisions and flexible scalar model settings, and a JSON API. Credential-like parameter names are rejected, but values are not secret-scanned; credentials must remain outside configurations. It does not implement the website UI, Agent Lab experiment definitions, datasets, benchmark evaluation/results, execution integration, Deep Agents, or AgentCore hosting.

The preferred initial execution direction is Deep Agents, its LangChain/LangGraph primitives, and Amazon Bedrock AgentCore Runtime, behind replaceable adapters. Generic experiment records should remain independent of framework and provider types.

The Python package and CLI retain the name `agent-orchestrator` until a later code migration. The CLI validates configuration; execution is exposed through Python APIs. The Codex adapter supports a bounded read-only report path with gated preflight and separate interruption/settlement evidence. Its broader effect-settlement guarantees remain incomplete. No live execution or deployment is established.

The six shipped workflows and eleven specialist profiles are retained because the current configuration loader and tests require them. They are legacy fixtures, not the project's future task queue or prescribed experimental topology. Generated schemas likewise describe the current legacy contracts.

## Set up and validate

Use Python 3.12+ and [uv](https://docs.astral.sh/uv/getting-started/installation/). SQLite is included with Python. Offline checks need no provider sign-in or AWS configuration.

```sh
uv sync --locked --group dev
uv run pytest -m 'not live'
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv lock --check
uv run agent-orchestrator --help
uv run agent-orchestrator --version
uv run agent-orchestrator validate-config config/project.example.toml
```

Live provider tests require explicit opt-in. See [development guidance](docs/DEVELOPMENT.md) for configuration validation, schema checks, and the boundary between local tooling and legacy runtime settings.

## Repository map

| Path | Current role |
| --- | --- |
| `AGENTS.md` | Project intent, operating principles, and authority |
| `docs/DEVELOPMENT.md` | Commands for the runnable legacy baseline |
| `src/orchestrator/` | Existing legacy runtime, separate from the Agent Lab backend |
| `src/agent_lab/` | Versioned catalog, SQLite composition persistence, and local JSON API |
| `docs/DISCOVERY_COMPOSITION_BACKEND.md` | Backend contracts, API routes, local boundary, and focused test command |
| `config/`, `presets/` | Configuration required by the current loader and regression suite |
| `schemas/` | Generated schemas for existing legacy models |
| `tests/` | Existing offline regressions and separately gated Codex live tests |
| `scripts/` | Existing configuration/schema checks and an optional Codex development launcher |

Git history preserves obsolete plans and research.
