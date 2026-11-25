# Agent Lab

Agent Lab is an open research project for defining and evaluating intelligent systems and the interfaces between their parts: agent to agent, agent to tool, model to model, and later perception to planner to controller. The central question is how each interface should represent information. The working principle is to use the cheapest representation that preserves what the next decision needs. Strong baselines and negative results are kept.

This repository is an early prototype. It contains a deterministic local orchestration foundation, a local discovery and composition API, and static research material. It does not yet run experiments against models, and it does not include a website UI.

## What works today

| Part | Status |
| --- | --- |
| Configuration validation (`agent-orchestrator validate-config`) | Works offline |
| Offline test suite (fake workers, local fixtures, no provider calls) | Works |
| Agent Lab discovery and composition JSON API (`agent-lab-api`) | Works locally, bound to loopback |
| Workflow execution, run CLI and UI | Not implemented |
| Live Codex runs | Opt-in only, see [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |
| Experiment definitions, datasets, benchmark results, Deep Agents, AgentCore hosting | Not implemented |

## Quick start

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/getting-started/installation/). SQLite comes with Python. No provider account or AWS configuration is needed for anything below.

```sh
git clone https://github.com/yanqinwang-cs/agent-orchestrator.git
cd agent-orchestrator
uv sync --locked --group dev
uv run pytest -m 'not live'
uv run agent-orchestrator validate-config config/project.example.toml
```

The last command should print `Valid example-project: config/project.example.toml`.

Start the discovery API in one terminal:

```sh
uv run agent-lab-api --port 8765
```

Then, in a second terminal, read the curated catalog:

```sh
curl http://127.0.0.1:8765/api/catalog
```

The API stores compositions in `~/.agent-lab/agent-lab.sqlite3` by default. Pass `--database PATH` to use another file. It listens only on `127.0.0.1`; do not expose it as a multi-user service.

## Checks

These are the same checks the GitHub `Checks` workflow runs on every push and pull request:

```sh
uv lock --check
uv run pytest -m 'not live'
uv run ruff check
uv run ruff format --check
uv run mypy --strict
uv run mypy tests scripts
```

Live provider tests are skipped unless you opt in with explicit environment variables. [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) explains the settings and the boundary between offline checks and live runs.

## Repository layout

| Path | Contents |
| --- | --- |
| `src/agent_lab/` | Versioned catalog, SQLite composition store, and the local JSON API |
| `src/orchestrator/` | Earlier deterministic orchestration runtime, validated configuration loader, and a pinned Codex adapter |
| `config/`, `presets/` | Example and development configuration read by the loader and its tests |
| `schemas/` | Generated JSON schemas for the orchestration models |
| `tests/` | Offline regression tests and separately gated live Codex tests |
| `studies/` | Static research material: a ceramic campaign study, a photo-condition study and a design handoff. These are not part of the installable package |
| `website/` | A local, static discovery preview with a frozen sample. See [website/README.md](website/README.md) |
| `docs/` | Development guidance and the Agent Lab backend contracts |
| `AGENTS.md` | The project's intent, operating principles and authority. Read it before contributing |

## Package details

- Distribution name: `agent-orchestrator`, version `0.1.0`. The name predates Agent Lab and is kept for now.
- Python: 3.12 or newer.
- Build: Hatchling. The wheel contains `orchestrator` and `agent_lab`.
- Runtime dependencies: `pydantic` and the exact pin `openai-codex==0.159.2` used by the Codex adapter.
- Console commands: `agent-orchestrator` (configuration checks) and `agent-lab-api` (the local API).
- License: MIT. See [LICENSE](LICENSE).
- This repository sets up no release to a package index. Install from a checkout with `uv sync`.

## AI assistance

Much of this repository was drafted with AI coding assistants under the maintainer's direction, and the maintainer reviewed the changes and ran the checks above. The design notes and studies are research drafts, not verified results. AI output can be wrong, so check claims against the code, the tests and the evidence before relying on them.

## Contributing

[AGENTS.md](AGENTS.md) is the authority for project intent and scope. Keep changes small, run the checks above, and explain what evidence supports a claim. Negative results are welcome.

## License

Released under the MIT License. See [LICENSE](LICENSE).
