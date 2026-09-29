# Development presets and environment

These six presets control **Codex used to build this repository**. They are development instructions, not product worker runtimes. Product specialists live in `presets/agents.toml`; their execution bindings follow the product contracts in `docs/IMPLEMENTATION_PLAN.md`.

The complete definitions are in `config/development.toml`; `scripts/codex_task.py` turns one into a documented CLI invocation. It uses the user's configured coding model unless `--model MODEL_ID` is supplied. Use a strong coding/reasoning model available to the account; use high effort for implementation, diagnosis, review and research, xhigh for cross-module architecture, and medium for routine test execution. If the selected model lacks that effort, select a supported value in the local development preset. Do not invent an entitlement-dependent model ID.

```sh
python3 scripts/codex_task.py implement --task-file tasks/01-foundation.md
python3 scripts/codex_task.py review --task 'Review the milestone 1 diff against its acceptance criteria.'
python3 scripts/codex_task.py architecture --task 'Assess a proposed change to the WorkerBackend contract.' --dry-run
```

| Preset | Purpose | Tool intention / sandbox | Expected output | Stop condition |
|---|---|---|---|---|
| implement | One bounded milestone or change | Read/edit/test; workspace-write | Working diff, focused tests, limitations | Acceptance met, or concrete unresolved prerequisite |
| architecture | Cross-module contracts and trade-offs | Read/search; read-only | Decision, affected contracts, migration and verification plan | Recommendation is concrete; implementation needs separate task |
| debug | Reproduce, classify, then fix | Read/edit/test; workspace-write | Reproduction, failure class, root cause, regression evidence | Verified fix or explicit unresolved cause |
| review | Independent code/spec assessment | Read/diff; read-only | Actionable findings with file/line evidence, or no findings | Scoped diff and relevant contracts assessed |
| test | Deterministic validation | Test commands; workspace-write for caches/temp files | Exact commands/results, failures classified | Requested validation complete; source edits require a separate implementation task |
| research | Narrow primary-source investigation | Read/search/web; read-only | Supported answer, sources, uncertainty and changed decision | Decision question answered; no broad market survey |

Sandbox settings are enforced by Codex. “Test only” or “review only” is task policy, not a command-level security sandbox. The launcher passes explicit effort, approval and web settings so repository defaults do not silently override its purpose. Research enables Codex web search; it does not grant unrestricted shell networking. All presets use user-reviewed escalation requests during development. Product workers separately use deny-all escalation.

## Skills and plugins

No plugin is required to begin. Optional skills, when already available and relevant:

- `codebase-design` for deep module boundaries and contract changes.
- `diagnosing-bugs` for failures whose cause is not established.
- `code-review` for an independent assessment of a scoped diff.
- `research` for primary-source integration questions; its procedure may delegate that research.
- `writing-for-agents` when changing `AGENTS.md` or execution instructions.
- `openai-docs` for current Codex SDK/configuration questions.

The launcher lists these as optional guidance; it does not install them or silently turn a missing skill into a dependency. Do not install an entire agent ecosystem to obtain one helper. An official documentation connection can help research but is not required at runtime. No long-term memory, browser automation, MCP marketplace or additional model-provider plugin is needed for v1.

Product context assembly is planned for milestone 7: explicit scoped inputs, provenance and a bounded context budget. Long-term memory remains disabled until a later extension defines its scope and persistence contract. The optional semantic `DecisionEngine` is a bounded decision interface, not a general-purpose manager or replacement for deterministic execution.

## Dependency policy

Milestone 1 is complete: `pyproject.toml` targets Python `>=3.12`, provides the console entry point and locks dependencies in `uv.lock`. The implemented runtime uses Pydantic v2 and the standard library (`sqlite3`, `tomllib`, `asyncio` and logging); application settings currently come from typed TOML, with no dotenv/settings package. Add FastAPI, Uvicorn and Jinja2 for the local UI in milestone 8, and add an environment-settings dependency only if a later contract needs it. Keep database writes in coordinator transactions and move slow filesystem/Git work off the request path.

Development tools: pytest, pytest-asyncio, Ruff, mypy and HTTPX when HTTP tests arrive. Add the pinned `openai-codex` SDK/CLI pair when implementing the Codex adapter in milestone 6. Recheck compatibility before selecting the version, then resolve and lock it with uv; do not treat the earlier integration-audit pin as a current release check.

When the UI arrives, one local Uvicorn worker should own one coordinator. Development reload must guarantee graceful coordinator teardown and ownership transfer; never run two schedulers against the same database. Keep default CI offline and fake-backed. SQLite is bundled with Python; no separate database installation and no Node toolchain are required.
