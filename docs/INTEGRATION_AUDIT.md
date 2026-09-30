# Runtime and Codex integration audit

Checked 28 September 2026. This is a source and configuration audit; **no live model calls, login changes or application runtime tests were performed**.

## First real harness backend: Codex

Codex is the planned first real worker backend because it fits the user's existing subscription-backed workflow. Keep it behind the provider-neutral `WorkerBackend`; do not make Codex types part of the domain contract. Through milestone 4, this repository implements only the scripted fake backend and its deterministic control/recovery behavior. The settings below record the SDK target selected for the adapter; they do not claim that the adapter is implemented.

Use the **official Python SDK, `openai-codex==0.147.0`**, behind `WorkerBackend`. The inspected PyPI distribution depends on `openai-codex-cli-bin==0.147.0`; use that matched pair initially. The locally installed standalone CLI is 0.154.0 and is a different compatibility target. Do not silently substitute it for the SDK's bundled binary. [PyPI metadata](https://pypi.org/pypi/openai-codex/json).

The SDK drives a local app-server and offers Python async APIs; a separate Node bridge and handwritten JSON-RPC client are unnecessary. Published source was downloaded without installation or execution and its wheel hash verified:

```text
openai_codex-0.147.0-py3-none-any.whl
sha256: ab2e0b3a41dba5a62be8561397cf3e7913afb53b5372ad881002a6f0b77e6a0a
```

In that wheel, `api.py` exposes `AsyncCodex.thread_start`, `AsyncThread.turn`, `AsyncTurnHandle.stream`, `steer` and `interrupt`, plus model listing and saved-thread reads/resume. `ApprovalMode.deny_all` maps to no escalation approvals; the default is `auto_review`, so override it explicitly. Sandbox values are `Sandbox.read_only` and `Sandbox.workspace_write`. The package has `CodexConfig.config_overrides`, `codex_bin`, `env` and `experimental_api`. Its process shutdown implementation terminates its app-server process; it does not establish a public guarantee of arbitrary descendant cleanup or crash reattachment. [Verified published wheel](https://files.pythonhosted.org/packages/3f/14/1a36ddc96152160768793689cd0924ffa78ce10e1bbb817fb4b006a96479/openai_codex-0.147.0-py3-none-any.whl).

| Integration | Fit | Decision |
|---|---|---|
| Python SDK | Typed local app-server client, streaming and live turn control; matched CLI package | Default; pin and test this pair |
| Raw app-server | Direct protocol access, but transport/lifecycle/types become our responsibility | Use only if a required stable capability is missing from SDK |
| `codex exec --json` | Simple batch worker with JSON events | Useful smoke/debug alternative; does not provide the same documented active-turn control interface |

The SDK docs describe local app-server operation; the server protocol documents thread/turn lifecycle and control. SDK stream completion must be interpreted from its terminal event, not from the last text fragment. Resuming a saved thread restores conversation state, not a previously suspended OS process. [SDK guide](https://developers.openai.com/codex/sdk), [app-server protocol](https://developers.openai.com/codex/app-server).

## Runtime families

Keep two worker-runtime families behind the same normalized contract:

- **Harness-backed runtimes** such as Codex and OpenCode already own an agent loop, tools, authentication and some permission enforcement. Their adapters start and control attempts, map events/results, and report actual capabilities.
- **Native/direct-model runtimes** such as a future Bedrock-backed runtime, provider APIs or local models require this application to own context/prompt assembly, tool schemas and execution, result filtering, stopping rules and model routing.

The coordinator remains the authority for topology, budgets, policy, concurrency, handoffs and persisted state in both cases. A runtime may report capabilities or a typed result; it cannot bypass coordinator checks. Profile identity should stay stable across approved execution bindings. V1 still fixes `AgentProfile.backend` and only allows model-binding overrides within that backend; the cross-runtime binding split requires a versioned contract change described in the [implementation plan](IMPLEMENTATION_PLAN.md).

## Authentication and permission boundaries

Codex supports ChatGPT sign-in and API-key authentication. This personal app can use Codex's sign-in flow with the user's existing subscription, subject to that account's model access and usage limits. The app must not implement OAuth, copy tokens into its database, or require an API key for this path. Use Codex's account preflight and login UI/CLI when needed. [Codex authentication](https://developers.openai.com/codex/auth).

Default the app's SDK subprocess to a dedicated `CODEX_HOME` containing app-managed harness settings; authenticate there through Codex if it has no account. This is a separate configuration context, not a new project account. Leave the user's normal Codex configuration unchanged. Record relevant project instructions/configuration in preflight; a dedicated home does not suppress trusted project settings. Expose inherited instructions separately from the app's assembled prompt. [Advanced configuration](https://developers.openai.com/codex/config-advanced).

Milestone 6 must demonstrate effective sandbox/network settings, disabled unintended integrations and no undeclared nested delegation under the pinned binary. Set narrow overrides through supported config surfaces; do not assume a tool-name list is enforced by Codex. If a project config or extension makes the requested restrictions unverifiable, preflight must report the mismatch before launch. Do not claim that an instruction prompt creates a security boundary.

A terminal turn receipt is not proof that unrelated descendant processes have stopped. The lifecycle owner needs bounded interrupt/shutdown checks, and unknown ownership must remain visible. Test this before enabling writer concurrency with real workers. No claim of exactly-once external side effects is made.

## Development configuration compatibility

Current Codex profiles are separate user-level files selected with `--profile`; project-local profile tables are not portable. Therefore this starter supplies real `.codex/config.toml` defaults plus a repository-owned preset launcher using documented CLI overrides. It never installs user profiles or rewrites the user's settings. Project configuration is loaded only after the project is trusted. [Configuration reference](https://developers.openai.com/codex/config-reference), [configuration layers](https://developers.openai.com/codex/config-advanced).

Local `codex --help`, `codex exec --help` and `codex app-server --help` were inspected; app-server JSON Schema was generated offline with CLI 0.154.0. This verifies available CLI/protocol surfaces, not runtime compatibility of every combination. Milestone 6's fixtures and optional live tests remain the compatibility gate.

Starter validation passed: all 11 TOML files parse; the 11 agents and six workflows pass basic reference/output/cycle checks; all six development launchers produce valid argument lists in dry-run mode; local Markdown links resolve. The proposed `.codex/config.toml` also validates against the [official configuration JSON Schema](https://developers.openai.com/codex/config-schema.json). These starter checks are lighter than the typed configuration validation delivered in milestone 1.

## Runtime comparison evidence

Deep Agents supplies an opinionated agent harness including context/filesystem facilities and subagent delegation. These overlap the worker harness already provided by Codex. Integration is possible, but adds model-facing delegation machinery that does not remove this app's scheduling and intervention ledger. [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [subagents](https://docs.langchain.com/oss/python/deepagents/subagents).

LangGraph supports ordinary Python nodes, explicit edges, branches and parallel execution. It does not require a model in the coordinator. Its checkpoint/history facilities and preservation of successful sibling work are genuine benefits. [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers).

The inspected `AsyncSqliteSaver` implementation commits checkpoint and pending-write operations itself; the inspected public interface does not establish a shared transaction with this app's attempt/event/reservation/outbox writes. That integration cost is the main reason to choose the bounded custom coordinator here. This is an architectural inference, not a claim that LangGraph cannot be made correct. [SQLite saver implementation](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/aio.py).

LangGraph interrupt resume restarts the interrupted node; replay can repeat subsequent external effects. Persisted graph state does not preserve a Python stack or external process. Application-level idempotency and reconciliation remain necessary. [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

Switch to LangGraph only when richer composition/history requirements justify it **and** it can own workflow progression without a competing application scheduler. Keep plain domain models and backend contracts so such a migration is possible. No framework benchmarks were necessary for this low-scale architecture decision.

## Evaluation boundaries

A model-controlled comparison holds the runtime, specialist profile, tools, assembled context, task and evaluation fixture constant, and changes only the model binding. A full-system comparison holds the task/evaluation fixture constant and compares complete runtimes such as Codex, native Bedrock or OpenCode. The first isolates model suitability; the second measures harness/runtime effectiveness. Record runtime and model with every result so a system-level difference is not attributed to the model alone.
