# Pre-M6 Codex architecture review

Reviewed 2026-09-30 at `c842b860ba990ca1858ae740c8f561bc268a8dd4` (`codex/research`), including the working canonical plan's previously approved CAND-003/004 refinements. M1–5 are implemented; Codex remains a target configuration. This review changes documentation and that version fixture only. No SDK install, login change, provider inference or production implementation occurred.

## Decision

Keep the official Python SDK, all eight `WorkerBackend` operations, the deterministic coordinator, immutable attempt specifications and both CAND-004 ownership pathways. Implement a conservative read-only Codex adapter in M6. Keep steering unavailable until consumed-input/result revision semantics can satisfy the existing contract. Require independently established execution settlement before a normalized terminal releases capacity. No ACP or `ToolOperation` is needed.

The architecture is sufficiently specified for offline implementation. **Real activation remains conditional:** the SDK alone does not prove sanitized launch configuration, host sandbox enforcement or descendant settlement. Task 6 starts by establishing these adapter-local guarantees; if they cannot be demonstrated, retain an explicit blocker and reject real launches. This review does not certify a working host integration.

## Evidence baseline

The current release checked was `openai-codex==0.159.2`, whose published metadata requires `openai-codex-cli-bin==0.159.2`. The downloaded wheel's SHA256 is `03c5a0d7c1da9edc4b62d7b4973d6e8199ce9462a7dec9c6dc9d75a2a88d3786`. Tag `rust-v0.159.2` resolves to commit `ff6aec96948b70d94983af2641a6b67c94faeff5`. This replaces the unimplemented 0.147.0 target; it is not an instruction to auto-upgrade later. [Version metadata](https://pypi.org/pypi/openai-codex/0.159.2/json), [published wheel](https://files.pythonhosted.org/packages/55/fd/89fa4ab1745e92dc8831f4a51ddc78ef216bfd5fcf3ca93c975c10555b77/openai_codex-0.159.2-py3-none-any.whl), [release source](https://github.com/openai/codex/tree/ff6aec96948b70d94983af2641a6b67c94faeff5).

Current [SDK documentation](https://learn.chatgpt.com/docs/codex-sdk) and [app-server documentation](https://learn.chatgpt.com/docs/app-server) establish intended public concepts. Version-specific claims below use pinned source. No practitioner sources were necessary.

## Challenged assumptions and decisions

Each refinement is needed before M6 acceptance. Persisted identity/enforcement mistakes are costly to repair after real attempts; implementation mechanisms can remain replaceable inside the adapter.

| Challenged assumption | Primary constraint | Decision before M6 | Reversibility and contract location |
|---|---|---|---|
| Convenience API is sufficient for effective preflight | High-level `thread_start` returns an ID wrapper; typed lower-level response retains settings | Use public typed SDK client, freeze actual response and configuration provenance before turn submission | Snapshot history cannot be reconstructed reliably later; versioned generic receipt, provider data translated at edge |
| Thread creation equals worker launch | Thread creation and turn submission are separate; turn API may join an active turn | Fresh non-ephemeral thread/client per attempt; one submission; no resume/replay for recovery | Adapter-local policy; persist identity because launch gaps are irreversible |
| Steer ACK supports effective input revision | Server queues input and returns turn ID | Steering unavailable in M6 with precise reason | Reversible capability choice; do not weaken generic `ControlAck` meaning |
| Terminal/interrupt/close prove stopped execution | Terminal is a turn outcome; SDK close has no descendant settlement receipt | Withhold generic terminal and known-terminal reconciliation until owned execution settles | Generic settlement invariant clarified; process control remains adapter-local |
| Saved history identifies live process | Fresh reader can synthesize interrupted for stored in-progress turns | Read history as evidence only; independently verify exact lifecycle owner | No new lifecycle state; existing unknown conservatively represents uncertainty |
| Dedicated home/env and tool list enforce isolation | Environment merges, multiple config layers, plugin disable list not enforcement | Verify sanitized launch and effective capabilities; fail mandatory unknown restrictions | Existing CAND-004 record refined; configuration mechanism remains local |
| Fake exception handling works for any backend | Coordinator catches `FakeBackendFailure` specifically | Add provider-neutral classified known-prelaunch failure seam during M6 | Small integration correction; preserve ambiguous errors as unknown, not generic retry |

Pinned source for API/response shape: [api.py](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/api.py), [async_client.py](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/async_client.py), [generated response types](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/generated/v2_all.py).

## Lifecycle and identity

`AsyncCodexClient` exposes `start`, `initialize`, `thread_start`, `turn_start`, `next_turn_notification`, `turn_interrupt`, `thread_read`, `account_read`, `model_list` and `close`. Use its public `request` with generated types for configuration reads. The SDK registers turn routing around submission to handle notifications arriving before the start reply. Cancellation of asynchronous wrappers cannot undo a request already transmitted. Keep bounded operation deadlines and retain late/uncertain receipts. [SDK client and routing](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py).

| Identity/evidence | Survives client restart / later inspection | Proves active execution? | Cancellation and attempt reuse |
|---|---|---|---|
| App attempt/owner UUID and prepared receipt | Yes in SQLite; receipt includes owner generation and runtime context | Intent alone does not prove launch or death | Authorizes only its own exact worker; never assign to a new attempt |
| Non-ephemeral Codex thread ID | Normally saved in Codex state; `thread_read` can retrieve history, subject to retention/access | No; a saved conversation is not a process | Useful address inside its owning server; no cancel guarantee through a new server; fresh thread on retry |
| Turn ID | Saved with thread history; receipt may be missing after a crash | Exact active server observations can prove activity; history alone cannot | Interrupt must match thread and turn on the owned client; never resend turn/start as a probe |
| Generic `session_id` | Nullable; do not invent another provider session identity or duplicate thread ID as process proof | No | Leave null unless a distinct verified provider session is actually supplied |
| App-server PID/process group | OS observation may outlive coordinator; PID reuse requires birth/generation evidence | Only while independently verified; process exit alone does not settle descendants | Adapter-local owner checks only; never kill an arbitrary/reused PID |
| Terminal result/history | Durable evidence only when retained and correlated | Proves neither process death nor all nested effects | Reuse validated result only after independent ownership settlement; no history deletion in `close` |

Steering appends pending input and returns an active turn ID; it does not establish which final response consumed that input. A client message ID and item-start event alone do not fix final revision attribution. Preserve this distinction rather than stamping an old answer with the newest requested revision. [Core input queue](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/session/turn_input.rs#L685), [official steering tests](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/tests/suite/v2/turn_steer.rs).

The exact-turn interrupt response ordinarily waits for `TurnAborted`; it is stronger than merely writing a request, but still not process cleanup. SDK close terminates, waits, then kills on failure without a second wait; no public descendant receipt is established. [Interrupt handler](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/turn_processor.rs#L1598), [SDK close](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py#L283).

Critical restart counterexample: thread reads use the reading app-server's local thread manager. When it has no active thread, stored in-progress turns can be presented as interrupted. Therefore a new client's terminal-looking view cannot release the original client's reservations. [Read path](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_processor.rs#L2824), [stale-turn status transformation](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_lifecycle.rs#L919).

## Capability and authentication ownership

| Capability | Service responsibility | Codex/OS responsibility or limitation |
|---|---|---|
| Workspace/filesystem | Authorize cwd and permissions, preserve source project, reject writing workflows before M7 | Execute reads/commands under verified sandbox; read-only is not a project-only read boundary |
| Terminal/process | Account for owner before launch; bound cleanup; preserve unknown reservations | Harness executes commands; SDK shutdown alone does not settle descendants |
| Network | Distinguish shell, harness provider traffic, web and integration policies | Runtime/OS enforce supported policies; no claim of a blanket offline harness while calling a model |
| Tools/integrations | Inspect effective availability; reject unverified mandatory restrictions; no app tool callbacks | Harness executes internal tools; internal effects remain opaque |
| Permissions | Coordinator applies outer ceilings; adapter rejects mismatch | Runtime/OS enforce actual sandbox; prompts and tool labels are intentions |
| Artifacts | Service retains bounded output bytes, hashes and validated generic receipts | Model output is untrusted; provider completion is not schema/content validation |
| Authentication | Persist availability/auth-method evidence only; offer actionable login error | Codex owns sign-in, credential storage and refresh; no tokens/account email copied to app DB |
| Lifecycle | Persist exact attempt/owner/thread/turn correlation; enforce release gate | Harness supplies turn/history evidence, not guaranteed cross-process reattachment |

Dedicated `CODEX_HOME` separates app-managed state but does not erase process environment or trusted/managed configuration. `CodexConfig.env` is additive. A supported adapter-local launch wrapper through `launch_args_override` may sanitize environment and establish ownership; its correctness is an implementation gate, not a capability proven by this review. Never modify the shared service environment between attempts. [Pinned launch implementation](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py#L195), [authentication](https://learn.chatgpt.com/docs/auth), [configuration layering](https://learn.chatgpt.com/docs/config-file/config-basic).

Deny-all approval means no escalation, not no tools. Read-only policy has shell network disabled by default in the inspected types, but effective permission profiles and legacy projections require verification. `disabledPluginIds` explicitly does not filter plugin capabilities. Inventory MCP, apps, plugins, hooks, nested agents, web search and persistent autonomous features; do not equate a schema key or override with demonstrated exclusion. Reject incompatible/unverifiable configurations before they can initialize unintended integrations. [Pinned configuration schema](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/config.schema.json), [permission derivation](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/config/mod.rs#L3600), [security guidance](https://learn.chatgpt.com/docs/agent-approvals-security).

## Events, reconciliation and M5

Normalize bounded progress/tool activity and output without exposing provider classes. Correlate thread/turn IDs before accepting lifecycle data. Success requires the matching terminal status, validated output and settled owner. Failed/interrupted statuses retain classification/evidence; partial output and missing usage remain partial/null. Ignore only demonstrably nonessential unknown events with bounded redacted diagnostics. Unknown lifecycle events, malformed terminal data, EOF without terminal and lost transport require attention unless exact terminal and settlement evidence can be independently recovered. Do not use the high-level collector's generic exception as failure classification. [SDK result collector](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/_run.py).

| Situation | Safe reconciliation |
|---|---|
| Crash before launch ACK, including after thread creation or turn send | Use any committed prepared identity, but missing receipt is not absence; remain unknown without exact evidence |
| Crash during turn / disconnect | Known running only from the exact owner; new reader history is insufficient; retain ownership |
| Uncertain interrupt | Do not replay blindly; inspect outcome and owner, otherwise unknown |
| Terminal received before local commit | Recover exact terminal/output evidence and independently settle owner before committing completion |
| Saved interrupted / missing history after restart | Neither proves original death or no launch; unknown by default |
| Known absent | Only authoritative proof no submission/execution remains, with preparation cleaned up; never infer from lookup failure |

Existing `Reconciliation` can represent running/terminal/cancelled/unknown. No new absent status is required: a proven prelaunch rejection may settle through the existing failure path; ambiguous absence remains unknown. Coordinator currently releases on terminal events and known-terminal inspection, so the adapter must satisfy that settlement invariant before returning them. Preflight failures that leave a client alive must also retain ownership.

M5 remains unchanged: worker model/runtime identity belongs to the attempt and preflight record; decision inference mechanism/calibration identity belongs to `DecisionEngine`. Resolve only approved worker bindings. No live decision routing or Codex-specific inference types enter M5.

## CAND-004 and CAND-005

CAND-004 survives. ACP v1 negotiates client capabilities; file operations can execute in the client environment, and terminal creation, exit, kill and release are distinct. A future ACP client would be this service, not the browser. This supports explicit execution/enforcement/settlement owners and alternate mapping fixtures without selecting ACP. [Initialization](https://agentclientprotocol.com/protocol/v1/initialization), [filesystem](https://agentclientprotocol.com/protocol/v1/file-system), [terminals](https://agentclientprotocol.com/protocol/v1/terminals). These versioned documentation pages were read on the review date; no ACP implementation/version dependency is introduced.

CAND-005 remains **proposed/unresolved**, retaining its evidence and deadline before M9 or earlier app-owned asynchronous/effectful callbacks. M6 excludes those callbacks. Harness-internal tools alone do not justify durable nested operations. No new deferred architecture candidate was needed.

## Delivery and limitations

Canonical §4 now records the exact target, preparation/snapshot ordering, steering limitation, configuration boundaries and settlement invariant. §5 clarifies the existing release rule; the M6 row points to the concrete task. The integration audit and target backend version match; the research queue retains compact accepted bookmarks and a detailed CAND-005.

Task 6 must demonstrate host isolation and owned process settlement before enabling real attempts. Source inspection cannot prove those guarantees, account entitlement, runtime quota, actual model availability or complete visibility into harness-internal effects. Offline implementation can proceed under the explicit activation gate; inability to establish it blocks real-backend acceptance, not permission to silently weaken the architecture.
