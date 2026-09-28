# Development presets and environment

These six presets control **Codex used to build this repository**. Product specialists live in `presets/agents.toml` and have different lifecycle and persistence rules.

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

## Dependency policy

Milestone 1 should create `pyproject.toml` with Python `>=3.12`, a console entry point and a committed `uv.lock`. Runtime foundations: Pydantic v2 and explicit dotenv/settings support; add FastAPI, Uvicorn and Jinja2 when implementing the UI. Use Python's `sqlite3`, `tomllib`, `asyncio` and standard logging. Serialize database writes in the coordinator; move potentially slow filesystem/Git work off the request path.

Development tools: pytest, pytest-asyncio, Ruff, mypy and HTTPX when HTTP tests arrive. Add `openai-codex==0.147.0` at milestone 5 and retain its pinned CLI dependency. Resolve and lock the actual compatible versions with uv; this starter does not present an ungenerated lockfile as reproducibility evidence.

One local Uvicorn worker owns one coordinator. For development reload, guarantee graceful coordinator teardown and ownership transfer; never run two schedulers against the same database. Keep default CI offline and fake-backed. SQLite is bundled with Python; no separate database installation and no Node toolchain are required.
