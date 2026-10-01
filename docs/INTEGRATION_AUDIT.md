# Runtime and Codex integration audit

Codex boundary rechecked 1 October 2026; other runtime comparisons retain their 28 September baseline. Pinned package, schema, persistence, scripted SDK lifecycle and local process-owner fixtures were validated offline; **no Codex account, thread, model or turn calls and no login changes were performed**.

## First real harness backend: Codex

Codex is the planned first real worker backend because it fits the user's existing subscription-backed workflow. Keep it behind the provider-neutral `WorkerBackend`; do not make Codex types part of the domain contract. The pinned adapter now implements preparation, one-turn submission, event mapping, exact interruption, bounded close and conservative reconciliation through the public Python SDK. Deterministic fixtures use a scripted SDK boundary and a separate local process owner; no live compatibility claim follows from those fixtures.

Use **`openai-codex==0.159.2`** with its exact dependency **`openai-codex-cli-bin==0.159.2`**. This supersedes the earlier 0.147.0 target. Do not substitute the standalone CLI or infer compatibility from a minimum-version check. [PyPI version metadata](https://pypi.org/pypi/openai-codex/0.159.2/json).

The published wheel was downloaded and inspected without installing or executing it:

```text
openai_codex-0.159.2-py3-none-any.whl
sha256: 03c5a0d7c1da9edc4b62d7b4973d6e8199ce9462a7dec9c6dc9d75a2a88d3786
runtime tag: rust-v0.159.2
source commit: ff6aec96948b70d94983af2641a6b67c94faeff5
```

[Pinned SDK wheel](https://files.pythonhosted.org/packages/55/fd/89fa4ab1745e92dc8831f4a51ddc78ef216bfd5fcf3ca93c975c10555b77/openai_codex-0.159.2-py3-none-any.whl).

The current uv environment separately reports both installed distributions at 0.159.2. Its SDK-bundled executable reports `codex-cli 0.159.2`; on this macOS arm64 host the inspected binary SHA-256 is `16593cc2f422d5f398a8e40f550ebbaf1245392528957be342c295920a300704`. The offline fixture at `tests/fixtures/backends/codex-sdk-0.159.2.json` labels this as synthetic environment evidence, not a captured provider run.

The SDK owns the local stdio transport. Prefer its public `AsyncCodexClient` typed methods for effective responses and notification routing: high-level `AsyncCodex.thread_start` discards effective thread settings. A typed `request` on that SDK for `config/read` is not a replacement transport. Keep experimental APIs disabled; do not implement raw app-server transport, a Node bridge or an alternate exec backend in M6. [Pinned SDK source](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex).

| Boundary | Verified constraint and M6 decision |
|---|---|
| Start | New thread is conversation preparation; turn submission starts work. Use a fresh client/thread per attempt and never replay ambiguous submission. |
| Steer | Acknowledges queued input, not consumed result revision. Advertise unavailable in M6 rather than advancing the ledger revision on this receipt. |
| Interrupt | Exact-turn response is cancellation evidence; it does not settle process ownership. Follow with bounded cleanup. |
| Close | SDK termination/kill does not prove reaping after kill or descendant settlement. Adapter settlement requires independent evidence. |
| Read/restart | A new reader can synthesize interrupted status for stored active turns. History existence or terminal-looking status does not prove the old owner died. |
| Async timeout | Cancelling an await cannot retract an RPC already sent. Preserve unknown launch/control outcomes. |

The [pre-M6 evidence review](research/PRE_M6_CODEX_REVIEW.md) contains pinned implementation links, identity/ownership matrices and the architecture decision record. The M6 task specification defines the activation preconditions. These are source-level findings, not completed host compatibility or live inference tests.

### M6 implementation state

SQLite schema v5 stores immutable preflight snapshots linked to attempts and immutable specification hashes. The coordinator commits a provider-neutral owner intent in the same transaction as attempt admission, reservations and dispatch intent, before preflight can launch a subprocess. It then commits the accepted snapshot and prepared thread/owner correlation before `turn/start`, and passes the record ID/hash to `start`; the fake path remains backward compatible. If preparation is interrupted before thread/turn identity is committed, the exact owner can be inspected but the submission outcome remains unknown. The adapter verifies the SDK/CLI pair, effective model/provider/effort, auth availability, config layers, thread permissions, instruction provenance and configuration stability before one turn. It maps typed SDK notifications into bounded provider-neutral progress/output, retains a single versioned JSON report and preserves partial/missing usage honestly.

`ProcessOwner` launches the pinned app-server with an allowlisted environment behind the public SDK `launch_args_override` bridge. It owns a dedicated process group, verifies the exact child/group identity, waits for the group to disappear and the bridge to disconnect, and writes a generation-bound receipt. Offline subprocess fixtures cover a child surviving app-server exit and service-parent loss; an unavailable or mismatched receipt remains unknown. The adapter rejects write requests, unreviewed integrations/features, unsupported outputs and configuration drift. Steering remains unsupported; interruption targets one persisted thread/turn and uncertain delivery is not replayed. A fresh reader's synthetic interrupted history remains unknown.

The offline suite does not establish that the pinned app-server's real configuration, account, model entitlement, thread response or live interruption behavior matches these fixtures. No account/model/thread/turn call or login change was made in this task. Treat live Codex acceptance as unverified until the separately guarded smoke tests run with explicit authorization; keep the milestone in progress and report any preflight rejection with its exact reason. `CodexConfig.env` inheritance, trusted/managed layers and the ineffective `disabledPluginIds` field remain fail-closed gates.

## Runtime families

Keep two worker-runtime families behind the same normalized contract:

- **Harness-backed runtimes** such as Codex and OpenCode already own an agent loop, tools, authentication and some permission enforcement. Their adapters start and control attempts, map events/results, and report actual capabilities.
- **Native/direct-model runtimes** such as a future Bedrock-backed runtime, provider APIs or local models require this application to own context/prompt assembly, tool schemas and execution, result filtering, stopping rules and model routing.

The coordinator remains the authority for topology, budgets, policy, concurrency, handoffs and persisted state in both cases. A runtime may report capabilities or a typed result; it cannot bypass coordinator checks. Profile identity should stay stable across approved execution bindings. V1 still fixes `AgentProfile.backend` and only allows model-binding overrides within that backend; the cross-runtime binding split requires a versioned contract change described in the [implementation plan](IMPLEMENTATION_PLAN.md).

## Authentication and permission boundaries

Codex supports ChatGPT sign-in and API-key authentication. This personal app can use Codex's sign-in flow with the user's existing subscription, subject to that account's model access and usage limits. The app must not implement OAuth, copy tokens into its database, or require an API key for this path. Use Codex's account preflight and login UI/CLI when needed. [Codex authentication](https://developers.openai.com/codex/auth).

Default the app's SDK subprocess to a dedicated `CODEX_HOME` containing app-managed harness settings; authenticate there through Codex if it has no account. This is a separate configuration context, not a new project account. Leave the user's normal Codex configuration unchanged. Record relevant project instructions/configuration in preflight; a dedicated home does not suppress trusted project settings. Expose inherited instructions separately from the app's assembled prompt. [Advanced configuration](https://developers.openai.com/codex/config-advanced).

Milestone 6 must demonstrate effective sandbox/network settings, disabled unintended integrations and no undeclared nested delegation under the pinned binary. Set narrow overrides through supported config surfaces; do not assume a tool-name list is enforced by Codex. If a project config or extension makes the requested restrictions unverifiable, preflight must report the mismatch before launch. Do not claim that an instruction prompt creates a security boundary.

The SDK's `env` merges with the service environment. A dedicated home therefore does not isolate credentials, proxy settings or integrations by itself. The adapter now routes SDK stdio through a private bridge to a separately launched app-server with an allowlisted environment, without mutating the service environment. Effective configuration and instruction sources are inspected through supported responses; retained provenance is redacted and hashed. `disabledPluginIds` does not enforce plugin exclusion. Deny-all approvals only deny escalation. Read-only does not mean project-only reads, and shell network policy does not cover harness model traffic, web search or external integrations. These host controls are covered by synthetic offline cases; live app-server behavior remains unverified.

A terminal turn receipt is not proof that owned descendant processes have stopped. The owner now checks direct-child reaping, process-group emptiness, bridge disconnect and an exact generation-bound receipt before the adapter emits a terminal event. The deterministic local fixture covers same-group child survival and service-parent loss. Do not infer live Codex tool-process behavior from that fixture: a host with unverified restrictions or cleanup must fail preflight or retain unknown ownership. No claim of exactly-once effects, active process reattachment or consumed steering revision is made.

## Development configuration compatibility

Current Codex profiles are separate user-level files selected with `--profile`; project-local profile tables are not portable. Therefore this starter supplies real `.codex/config.toml` defaults plus a repository-owned preset launcher using documented CLI overrides. It never installs user profiles or rewrites the user's settings. Project configuration is loaded only after the project is trusted. [Configuration reference](https://developers.openai.com/codex/config-reference), [configuration layers](https://developers.openai.com/codex/config-advanced).

Historical 28 September check: local `codex --help`, `codex exec --help` and `codex app-server --help` were inspected; app-server JSON Schema was generated offline with CLI 0.154.0. This verifies available CLI/protocol surfaces, not runtime compatibility of every combination. Milestone 6's fixtures and optional live tests remain the compatibility gate.

Starter validation passed: all 11 TOML files parse; the 11 agents and six workflows pass basic reference/output/cycle checks; all six development launchers produce valid argument lists in dry-run mode; local Markdown links resolve. The proposed `.codex/config.toml` also validates against the [official configuration JSON Schema](https://developers.openai.com/codex/config-schema.json). These starter checks are lighter than the typed configuration validation delivered in milestone 1.

## Runtime comparison evidence

Deep Agents supplies an opinionated agent harness including context/filesystem facilities and subagent delegation. These overlap the worker harness already provided by Codex. Integration is possible, but adds model-facing delegation machinery that does not remove this app's scheduling and intervention ledger. [Deep Agents overview](https://docs.langchain.com/oss/python/deepagents/overview), [subagents](https://docs.langchain.com/oss/python/deepagents/subagents).

LangGraph supports ordinary Python nodes, explicit edges, branches and parallel execution. It does not require a model in the coordinator. Its checkpoint/history facilities and preservation of successful sibling work are genuine benefits. [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers).

The inspected `AsyncSqliteSaver` implementation commits checkpoint and pending-write operations itself; the inspected public interface does not establish a shared transaction with this app's attempt/event/reservation/outbox writes. That integration cost is the main reason to choose the bounded custom coordinator here. This is an architectural inference, not a claim that LangGraph cannot be made correct. [SQLite saver implementation](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-sqlite/langgraph/checkpoint/sqlite/aio.py).

LangGraph interrupt resume restarts the interrupted node; replay can repeat subsequent external effects. Persisted graph state does not preserve a Python stack or external process. Application-level idempotency and reconciliation remain necessary. [Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence).

Switch to LangGraph only when richer composition/history requirements justify it **and** it can own workflow progression without a competing application scheduler. Keep plain domain models and backend contracts so such a migration is possible. No framework benchmarks were necessary for this low-scale architecture decision.

## Evaluation boundaries

A model-controlled comparison holds the runtime, specialist profile, tools, assembled context, task and evaluation fixture constant, and changes only the model binding. A full-system comparison holds the task/evaluation fixture constant and compares complete runtimes such as Codex, native Bedrock or OpenCode. The first isolates model suitability; the second measures harness/runtime effectiveness. Record runtime and model with every result so a system-level difference is not attributed to the model alone.
