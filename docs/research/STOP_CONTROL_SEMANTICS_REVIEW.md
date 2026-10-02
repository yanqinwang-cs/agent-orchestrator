# Stop, interrupt, cancellation and settlement across runtimes

**Date:** 2026-10-02. **Status:** non-canonical research and proposals awaiting human approval. **Repository baseline:** `c55c20a8d43734e49ee6762b58d74dc5f60c5c14`, `codex/research`, plus the existing Task 06b working changes. Source observations refer to that working tree, not just HEAD. No canonical plan, implementation task, production source or candidate backlog was changed by this review.

## 1. Executive recommendation

Keep one product intent: **stop this attempt from continuing**. Preserve the small `interrupt` / `close` / `inspect` boundary for now, but make its interpretation truthful: requesting cancellation, observing the execution outcome and proving scoped settlement are independent facts. Most provider primitives should remain adapter-local. Do not expose a separate generic method for every provider's abort, stream close, signal, session disposal or job API.

The current abstraction is **usable but its receipt/state mapping is too overloaded**. `ControlAck.accepted` cannot universally mean cancellation completed, and `ShutdownReceipt.settled` must mean the admitted ownership/effect scope is settled, not merely that one child died. An accepted control may race with normal completion; a rejected control may be followed by independent successful termination. Neither permits rewriting the earlier receipt. Keep the provider outcome, control outcome and settlement evidence distinct. Findings below support adapter-local mapping first, followed only by additive evidence semantics where the coordinator actually needs them.

The smallest M6 correction is concrete: align the interrupt fixture and response parser with pinned Codex's empty `{}` result, retain sanitized rejection details, and test normal-completion/cancellation races. **That does not explain the recorded live rejection, nor make an empty success response proof of an interrupted turn.** Keep exact targeting and current fail-closed acceptance until validated. Any proposal to terminate after rejected/uncertain cancellation is a separately approved control-policy change, not a silent fallback or a way to pass the exact-interrupt test. No generic storage migration is needed to establish or repair the pinned response-shape mismatch.

The architecture candidate for human review is a bounded, policy-selected stop procedure: prevent further admission, request the profile's narrowest safe cancellation, optionally terminate/revoke only exclusively owned resources, and independently reconcile the required scope. Preserve every phase's evidence. Never kill a shared inference server to stop one request. Unknown effects retain `outcome_unknown` and reservations; timeout is a deadline trigger, not successful cancellation. The candidate queue remains untouched under repository isolation policy.

## 2. Current contract and implementation evidence

Read the canonical [implementation plan](../IMPLEMENTATION_PLAN.md), [integration audit](../INTEGRATION_AUDIT.md), [authority review](CROSS_RUNTIME_AUTHORITY_REVIEW.md), [Task 06](../../tasks/06-codex-harness-backend.md), [Task 06b](../../tasks/06b-cross-runtime-authority-policy.md), and affected backend/coordinator/owner/live-test contracts. Task 06b's original planning text remains historical: current source and audit record the correction as implemented. The audit reports 189 offline passes and a post-correction `gpt-5.6-luna` read-only smoke pass, followed by rejected exact-turn interruption and settled cleanup. These are existing recorded results; this review ran no live tests and does not certify them anew.

| Current surface | Observed meaning and limitation |
|---|---|
| [`BackendCapabilities`, `ControlAck`, `ShutdownReceipt`](../../src/orchestrator/domain/backend.py) | `interruption` is Boolean; the ACK has command ID, accepted/supported and free-text reason; shutdown has settled/detail. There is no typed distinction between received, accepted, observed terminal or settled coverage. |
| [`WorkerBackend`](../../src/orchestrator/backends/protocol.py) | Separate `interrupt(handle, command_id)`, `close(handle)`, `inspect(identity)` already provide useful cancellation/cleanup/reconciliation seams. No need to replace all eight methods for this research. |
| [`Coordinator._add_interrupt_intent`](../../src/orchestrator/execution/coordinator.py) | Persists command/action/attempt identity, exact handle/thread/turn, cancel-requested state and outbox before delivery. Retries and revisions remain deterministic. |
| [`Coordinator._dispatch_control_action`](../../src/orchestrator/execution/coordinator.py) | Rejection restores running/attention; timeout/exception becomes unknown and inspection. Only accepted interrupt proceeds directly to bounded `close()`. Thus rejection currently prevents this coordinator path from escalating cleanup. The live test's `finally: close()` is a different path. |
| Coordinator accepted branch | Successful provider ACK is not separately committed before close. Close failure produces an overall unknown record, with only some paths preserving ACK knowledge in prose. Accepted ACK + settled close can mark the attempt cancelled/timed-out and `safe_to_retry=True`. That mapping must not be generalized to remote/effectful profiles or normal-completion races without additional evidence. |
| [`CodexBackend.interrupt`](../../src/orchestrator/backends/codex_backend.py) | In-memory command/target deduplication, exact owner/thread/turn checks, bounded RPC, `InvalidRequestError` collapsed into a generic rejection; successful response incorrectly expected to echo `turn_id`. The pin's response model is empty. |
| [`OfflineCodexSDK`](../../tests/test_codex_backend_lifecycle.py) | Supplies `SimpleNamespace(turn_id=...)`, unlike the installed SDK response; it masks the success-path mismatch. |
| [`CodexBackend.inspect`](../../src/orchestrator/backends/codex_backend.py) | Requires original-owner evidence; synthetic interrupted history alone is unknown. Current policy also requires accepted interrupt evidence before treating interrupted history as known cancellation. Preserve this policy unless explicitly changed. |
| [`ProcessOwner`](../../src/orchestrator/backends/codex_owner.py), [owner tests](../../tests/test_codex_owner.py) | Starts the app-server in a new session; TERM then KILL its process group, reap direct child, verify group emptiness/bridge disconnect and generation-bound receipt. Tests cover same-group survival, not a general detached process tree or remote effect boundary. |
| [Live tests](../../tests/test_codex_backend_live.py) | Short report may complete before interrupt; successful completion before control is inconclusive. Cleanup runs even after control failure, so settled cleanup must not be reported as accepted exact-turn interruption. |

The current authority projection calls the process scope an attempt process group while listing descendant ownership and no known gaps. A group is not a tree. This research identifies a coverage question: no evidence inspected here proves that every reachable descendant must remain in that group. State that limit rather than inferring a containment guarantee from the group receipt. This is a scoped finding, not an implemented containment fix.

## 3. Evidence-derived minimal vocabulary

Use two operations already present, plus observations: **request cancellation of scoped work**, **settle/dispose owned execution resources**, and **inspect/reconcile evidence**. A stop procedure composes them under policy. Exact-operation versus current-active targeting belongs in the admitted profile/receipt, not necessarily in separate product commands. “Graceful worker stop” is a policy sequence, not a universally available primitive. “Effect settlement” is a verified condition, not another synonym for cancel. Session disposal is separate when a runtime offers it; disposal may remove observability without stopping work.

| Distinction | Real evidence requiring it | Generic need and minimum treatment |
|---|---|---|
| Intent versus mechanism | Codex turn interrupt, Claude current interrupt, direct HTTP close, OS TERM | Coordinator persists intent; adapter chooses only permitted mechanisms. A rename alone adds no correctness. |
| Exact operation versus active work | Codex target validation versus ACP/OpenCode session cancellation and Claude current interrupt | Preserve binding/target scope. Active-work control is admissible only with exclusive attempt binding and no successor admission; never silently retarget shared/reused sessions. |
| Delivery/ACK versus execution outcome | Codex success on normal completion; optional ACP request cancellation; async engine abort | Coordinator must not infer cancelled from an ACK alone. Record observed status independently. |
| Execution ended versus ownership/effects settled | Local subprocess groups, background ACP jobs, direct-model application tools | Required before reservation release and retry. Keep profile-scoped settlement evidence and known gaps. |
| Session reuse/disposal | Claude drains/reuses, Codex resume, remote sessions surviving client disconnect | Adapter-local unless policy requests reuse. M6 still uses a fresh client/thread per attempt and does not resume retries. |

These distinctions are needed for safe admission/recovery; a universal catalog of provider commands is not. Mechanisms and raw provider statuses remain adapter-local. A future normalized receipt may add target scope, mechanism/evidence reference and stage outcome, but only when a deterministic branch consumes those values. Do not parse free-text diagnostics to make recovery decisions.

## 4. Requests, receipts, observations and settlement

The following are separate facts, not a linear ladder where one automatically proves all predecessors:

| Fact | Sufficient evidence for that fact | What it does not establish |
|---|---|---|
| Control requested | Durable authorized command and target/policy | Delivery |
| Delivery attempted | Durable action claim and transport attempt | Peer receipt; packet write may precede disconnect |
| Control acknowledged | Correlated protocol response with preserved meaning | Target accepted cancellation, unless that protocol says so |
| Cancellation accepted | Profile-defined response/event for the target | Generation ended, tool completion or effect rollback |
| Generation stopped | Authoritative generation termination evidence | App/harness tool execution ended |
| Turn terminal | Correlated terminal observation and status | Cause, prior ACK or process settlement |
| Owner exited | Exact process/job identity plus wait/status evidence | Detached descendants or remote jobs ended |
| Descendants settled | Verified membership/containment and quiescence evidence | Remote effects settled; completed effects undone |
| External effects settled | Relevant executor/job/broker's authoritative scoped evidence | Rollback or retry safety of already completed effects |
| Artifacts finalized | Retained bytes, local hashes, required schema/lineage validation | Control succeeded; partial output becomes a successful result |
| Session reusable | Provider contract and drained/consistent session state | Permission to reuse it for this product's retry policy |

A later terminal observation can resolve execution status without fabricating an earlier control ACK or cancellation cause. Conversely, absent ACK does not imply the request failed. Keep this causality distinction even if the UI eventually has one Stop button. The present M6 policy may conservatively remain unknown where it demands unavailable exact cancellation evidence.

## 5. Codex: pinned mechanisms and the thirteen questions

The exact audited SDK/CLI version is **0.159.2**, source `ff6aec96948b70d94983af2641a6b67c94faeff5`. These source-level findings are stronger than guessing from the generic live-test error, but do not reproduce that error.

| Mechanism | Target / initiator → acknowledger | Receipt, scope and limits |
|---|---|---|
| `turn/interrupt` with nonempty ID | Client → app-server, thread + requested turn | Correlated empty RPC result after a terminal event drains pending requests; normal completion can do this too. Not a process/effect receipt. |
| Empty-ID startup interrupt | Client → app-server, startup/current core work | Acknowledged after submission, without waiting for a turn terminal. Different semantics; prohibited as a fallback for this exact-turn profile. |
| `command/exec/terminate` | Client → app-server, connection-scoped process ID | Control loop accepts termination before exit necessarily arrives; unknown command rejects. Connection teardown also requests termination of that connection's commands. |
| Experimental background-terminal termination | Client → app-server, thread + tracked terminal process ID | Returns `terminated`; targets managed terminal work, not the turn or arbitrary descendants. Outside M6's experimental-disabled profile. |
| `thread/unsubscribe` | Client → app-server, thread subscription | Subscription status only; busy work is not synchronously stopped. Idle unload later requests bounded shutdown. |
| `thread/archive` | Client → app-server, loaded thread/subtree plus storage | Requests shutdown then archives, but can proceed after shutdown failure/timeout. Neither a stop receipt nor appropriate Stop replacement. |
| SDK `close()` | Client owner → direct subprocess | stdin close, terminate, wait two seconds, kill on exception; no second wait after kill. This targets the bridge in our launch arrangement. |
| Server signal / internal shutdown / OS kill | Supervisor or user → app-server / kernel | First TERM/Ctrl-C drains existing turns; subsequent forceable signal can force shutdown. Internal cleanup and force death have different guarantees. |

Sources: [turn handler][C1], [command termination][C6], [background terminal control][C7], [unsubscribe][C8], [archive/shutdown][C9], [SDK close][C10], [signal/drain handling][C11].

**1. SDK promise.** Sync `turn_interrupt` submits the caller's thread/turn pair via public JSON-RPC; async wraps that call in a worker thread. Return type `TurnInterruptResponse` has no fields. Request-ID correlation belongs to the SDK; no echoed turn or caller command deduplication is supplied. Cancelling the Python await cannot retract a sent RPC. [SDK sync][C2] / [SDK async][C3] / [protocol schema][C4]

**2–3. Valid states and rejections.** The handler first loads the thread. A conflicting active turn rejects; absent active state with a matching last-terminal ID or non-running agent rejects as no active work. If the active snapshot is absent but the agent is running and the requested turn is not the last terminal, submission is allowed without a positive active-ID match. Thread-load and core-submission failures are separate. No source justifies assigning the recorded live error to one branch without its original diagnostic. [Turn validation][C1] / [pinned interrupt tests][C5]

**4. Races and idempotence.** Validation and targetless core `Op::Interrupt` submission are separate: core subsequently cancels its current task. The exact target check is not a universal atomic compare-and-cancel guarantee. Both `TurnComplete` and `TurnAborted` send pending `{}` responses before the associated completion notification. Duplicate requests can share that event; a later duplicate can reject after completion. Thus neither generic idempotence nor successful cancellation follows from `{}`. M6's one-turn/no-successor policy narrows this race without changing the upstream contract. [Terminal handlers][C12] / [pending response drain][C13] / [core active task][C14]

**5. Other primitives.** The mechanisms above address different objects. Realtime-stop, login cancellation and search cancellation are operation-specific, not general worker controls. Unsubscribe/archive are particularly poor substitutes: one removes observation and the other mutates retained history while tolerating shutdown failure. [Unsubscribe lifecycle][C8] / [idle unload][C15] / [archive][C9]

**6. TUI and CLI.** TUI Stop uses the same turn RPC, but permits an empty startup target and retries once using the server-reported current ID after mismatch. This is active-work UX policy. `codex exec` Ctrl-C uses its task ID, logs failure, and later tears down its subscription/server. Neither authorizes this coordinator to retarget another turn or call cleanup an exact interrupt pass. [TUI routing][C16] / [CLI control][C17]

**7. Client close.** SDK close is bounded direct-child plumbing, not a durable tree receipt. Our adapter's independent owner termination and exact generation checks remain necessary. A completed async close call does not strengthen the underlying process/effect guarantee. [SDK close][C10] / [local settlement code](../../src/orchestrator/backends/codex_backend.py)

**8–10. Process death and descendants.** Server TERM initially requests drain; it may let active turns finish. Internal `Op::Shutdown` aborts tasks, stops hooks/tracked execution and MCP/runtime components, flushes history and emits shutdown completion, subject to bounded server teardown. Force KILL bypasses that cleanup. Turn abort itself allows 100ms cooperative cancellation before aborting the task, runs task/hook cleanup, records interruption and may start pending work; it is not global background-terminal shutdown. [Drain][C11] / [session shutdown][C18] / [task abort][C19] / [pending continuation][C20]

Pinned Codex managed command code supports its **own process groups/new sessions**, group interrupts/kills, and Linux-specific parent-death behavior; remote exec uses separate controls. Consequently even a non-malicious managed command can lie outside the app-server's process group. Killing only that group is not a general command-tree settlement proof on macOS. The source supplies managed-group helpers, not a universal RPC receipt covering every detached/remote descendant. Existing M6 tests prove only their declared same-group case. [Group helpers][C21] / [command session creation][C22] / [local and remote unified execution][C23]

**11. History.** Real interruption records a marker and attempts flush, but flush errors and missing command receipts remain possible. More decisively, the history reader can convert saved `inProgress` to `interrupted` when no active state is recognized. That is an observation produced by the reader, not acknowledgement or original-owner death. [History normalization][C24] / [task abort and flush][C19]

**12. Reuse.** Interrupted loaded threads can continue; core can schedule pending work. Saved threads can be resumed after process death, but an unsaved tail, external effects and synthetic states prevent treating resume as execution reattachment. Product policy still requires a fresh client/thread for every M6 attempt. [Pending continuation][C20] / [history normalization][C24]

**13. Remote effects.** Cancelling the core token exits local model-stream handling; no inspected receipt proves provider computation, remote commands or previously issued external effects stopped. Completed writes are not undone. Those surfaces must be excluded, independently constrained or tracked by the admitted profile. [Model stream cancellation][C25] / [remote execution distinction][C23]

## 6. Claude and OpenCode: active work, tasks and owner teardown

Comparative pins: Claude Python SDK `bfb895c6ef46e095191938b4eda798a025957c09` (0.2.163), OpenCode `1ddb0873aee50d209d1a8d7f91b89c5daf692d49` (1.18.34). Claude Code binary/versioned TypeScript receipt support is a separate deployment concern; current docs are not a guarantee for every SDK/CLI pair.

| Mechanism | Target / initiator | Receipt and timing | Limits |
|---|---|---|---|
| Claude Python `ClaudeSDKClient.interrupt()` | Current query in streaming client; request has subtype `interrupt`, no exact turn ID. Caller initiates. | Awaits correlated CLI `control_response`; CLI error raises, transport loss/60-second timeout is unknown. Later receive `ResultMessage`. | Python wrapper discards success payload. This is current-active cancellation, not an exact operation compare-and-cancel. Stale target detection and semantic idempotence are not promised. A retry after new work starts can stop different work. [source H1][H1] / [source H2][H2] |
| Claude TypeScript `Query.interrupt()` | Current query; streaming input required. | Current docs: optional versioned `interrupt_receipt_v1`, CLI >=2.1.205, lists pending main-thread message UUIDs at processing time. | Queued work may start immediately after interrupted result. `interrupt()` does not cancel queued messages. Raw control `cancel_queued:true` is a separate capability >=2.1.219; old CLIs ignore it. Empty receipt does not prove no future work (messages without UUID and subagents excluded). [source H3][H3] |
| Claude `stop_task(task_id)` / TS `stopTask(taskId)` | Exact background task identity from task-start frame. | Control response, then terminal TaskUpdatedMessage (`killed`) or TaskNotificationMessage (`stopped`); notification may be suppressed. | Task outcome must be observed separately. Stops background task rather than treating whole client or main turn as the only target. No promised rollback or universal remote-effect settlement. [source H1][H1] / [source H2][H2] |
| Claude permission deny with `interrupt=True` | Application permission callback rejects proposed tool and interrupts current execution. | `ResultMessage.terminal_reason` can be `aborted_tools` or `aborted_streaming`. | Same terminal reason can arise from a permission decision or explicit interrupt; history does not identify which control command was acknowledged. [source H4][H4] |
| Claude Python `disconnect()` / context exit | Query, in-process MCP bridge, and owned CLI subprocess. | Cancels SDK child tasks/tools, closes transport; default transport stdin EOF→wait 5s→TERM→wait 5s→KILL→wait 5s. | Bounded best-effort direct-child cleanup; raw asyncio cancellation can disrupt shielding; custom transports/store callbacks have separate bounds. A cancellation-resistant in-process worker-thread tool is abandoned after a grace period. Child exit is not detached-descendant or remote-tool settlement. [source H1][H1] / [source H2][H2] / [source H5][H5] |
| Claude TS `Options.abortController` / `Query.close()` | Query/process lifetime, not exact turn. | `close()` returns void. Spawn signal teardown happens after stdin close and about 2s grace on caller abort. | Public docs promise process teardown, but a return from void close is no independent process-tree/effect receipt. Custom process launcher owns proper teardown. [source H3][H3] |
| Claude Code interactive Esc | Current response/tool; user interface dependent. | Visible interruption; keeps completed work. | Queued messages can run next; Esc is not session disposal. Dialog/permission context changes meaning. [source H6][H6] |
| OpenCode `POST /session/:id/abort` / SDK session.abort | Current work of exact session identity, no exact turn. | HTTP handler awaits cancel then returns `true`; no distinct already-terminal/stale-target outcome. | Pinned cancel walks currently registered related running background jobs, cancels current runner, awaits fiber interruption/cleanup and marks idle. Missing runner simply becomes idle. A duplicate without intervening work is harmless in this implementation; retry across new work is not exact-target safe. [source H7][H7] / [source H8][H8] / [source H9][H9] |
| OpenCode server `close()` / SDK AbortSignal | Spawned whole server or TUI process. | Calls process stop; no awaited exit receipt. | POSIX `proc.kill()` direct child; Windows `taskkill /T /F`, fallback direct child. Can affect every session hosted there. Not equivalent to session abort; cannot claim process-tree settlement on POSIX. [source H10][H10] / [source H11][H11] |

For Claude, drain the interrupted result before reading the next query's response. Transcript persistence supports conversation reuse, not cancellation-command reconstruction. Forced exit can lose the final persisted message; completed file writes remain. OpenCode's background-job registry is process-local and expressly lacks restart recovery. It can expose `cancelled` status before job-scope close completes; an HTTP abort return that awaited cleanup is stronger than polling that intermediate label, but neither proves arbitrary detached/external effects. [Claude drain][H4] / [Claude teardown][H5] / [OpenCode registry][H18]

**Materially different remote profile — Claude Managed Agents:** `user.interrupt` is a persisted event; enqueue acknowledgement precedes its `processed_at` observation and eventual idle. Tools may delay processing. Thread selection can name one thread or broadcast to all non-archived threads. Eventual `end_turn` also occurs on normal completion, so it cannot identify a specific interrupt's success alone. The terminal client's Ctrl-C detaches while remote work continues; Esc sends interrupt. Running sessions cannot simply be archived/deleted instead of stopped. Artifact delivery can lag idle. These are remote session/job semantics, not the local Claude SDK process model. [Event processing][H19] / [target scope][H20] / [detach versus interrupt][H21] / [session operations][H22]

## 7. Direct inference, local engines and durable remote jobs

Endpoint/profile identity matters. Bedrock Converse, Bedrock Responses on two endpoints, OpenAI synchronous/background Responses, local engines and durable batch jobs expose different cancellation contracts. For every row, an unmentioned guarantee is **not established**, rather than assumed to match another API's method name.

| Mechanism | Target / initiator | Receipt / timing | Idempotence and races | Residual effects and restart |
|---|---|---|---|---|
| Bedrock Converse / ConverseStream / InvokeModelWithResponseStream client transport cancellation | Application cancels its HTTP call/event stream; scope is that transport, not a separately named durable generation | No exact invocation-cancel endpoint or cancellation acknowledgement is documented in the inspected API contracts. Closing the client releases its transport; remote completion timing is **unknown** | Cancellation can race natural completion; loss of stream cannot distinguish service stop, continued generation, or response loss. No provider idempotence guarantee for a cancellation request because this surface has no such request | Preserve received deltas as incomplete evidence. `messageStop` is model-message completion, not app-tool settlement. No per-request GET/status/replay API is documented on these Converse/Invoke surfaces; application owns conversation/history and tool records [source I1][I1] / [source I2][I2] / [source I3][I3] |
| OpenAI synchronous Responses / stream close | Caller closes the associated connection | Official guide describes this as synchronous cancellation; SDK closes HTTP response without separate cancel receipt [source I4][I4] / [source I5][I5] | Completion can win; no inspected bounded provider/tool-settlement guarantee | Retain partial output. Stored retrieval, where available, is later state evidence; application tools need separate control |
| OpenAI background Responses cancel | Caller targets exact response ID | Returns Response; inspect status. Dropping the stream leaves background execution running [source I4][I4] | Repeated cancel explicitly idempotent; normal completion may win | Persist ID for retrieval within retention limits; cancellation does not undo effects or settle app tools |
| Bedrock Responses on **bedrock-runtime** `POST /openai/v1/responses/{id}/cancel` | Caller targets response ID, with project authorization and correct serving region | AWS explicitly lists cancel for a still-in-progress response while also stating `background=true` is rejected (400). Do not import OpenAI's background-only restriction or generalize this to Converse [source I6][I6] | Current inspected AWS page does not specify repeated-cancel idempotence or already-terminal race response. Treat as unknown until profile evidence. 404 cannot distinguish never-existent/wrong-account/not-stored; region also matters | Stored response retrieval supports reconciliation when identity and storage survive; `store` defaults true, retention 30 days. Server-side tools unavailable on this endpoint; client tools remain application-owned [source I6][I6] / [source I7][I7] |
| Bedrock Responses on **bedrock-mantle** | Distinct Responses endpoint, background and server-side-tool support differ from bedrock-runtime | Shared API shape is insufficient to import detailed cancel guarantees; exact acceptance/idempotence/effect-settlement contract needs separate profile verification | Do not assume AWS matches OpenAI error/race semantics solely from SDK compatibility | Responses may invoke Lambda tools remotely; cancelling response is not evidence Lambda/external effects stopped or reverted [source I6][I6] / [source I7][I7] / [source I8][I8] |
| Ollama JS iterator `.abort()` / client `.abort()` | Iterator uses its AbortController; client method iterates **all currently tracked streamed requests** for that client instance [source I9][I9] / [source I10][I10] | Synchronous local controller action; stream consumer gets AbortError. This is not a server cancellation receipt | Repeating on an already aborted controller is a local no-op, not evidence of provider idempotence. Finish/registration/disconnection races remain; client-wide abort has broader scope than one attempt. No stale-target distinction from server | Local stream fragments remain; application decides history and tools. Native generate/chat API does not expose durable generation lookup/cancel ID for restart reconciliation [source I11][I11] / [source I12][I12] |
| Ollama native local request cancellation propagation | Server derives completion context from incoming request; llama-server runner makes upstream request with that context and returns context errors [source I13][I13] / [source I14][I14] | Source proves cooperative cancellation propagation through HTTP contexts; it does **not** establish a bounded GPU-settlement acknowledgement | Endpoint/binary/runner dependent, race with completion. Avoid stronger guarantee for cloud-forwarded Ollama or a different runner without inspection | Model resident state and server stay reusable; no durable cancellation receipt is specified. Ordinary tool-calling guide executes tools in client code [source I12][I12] |
| Ollama runner close / model unload | Runner Close kills its direct llama-server process and waits for its done channel. `keep_alive=0` is model residency/unload behavior, not an exact generation cancel contract [source I11][I11] / [source I14][I14] | Internal Close waits direct process termination. Model unload may affect shared users and is not an approved generic attempt stop | Whole runner scope; do not equate process death with detached descendants/remote effects | Inference: safe escalation requires exclusive ownership and independent settlement, not killing a shared server |
| vLLM `AsyncLLM.abort(request_id, internal=False)` | Application targets request ID; external ID resolves all associated internal requests; parallel sampling parent aborts children [source I15][I15] / [source I16][I16] | Frontend removes states and emits final ABORT output, then engine-core client asynchronously sends ABORT. Return is not an engine-stop receipt in this path [source I15][I15] / [source I16][I16] / [source I17][I17] | Unknown/already-removed mapping yields empty work and no informative rejection; duplicate is effectively no-op for absent mapping. External ID reuse can target new work; require unique scoped identity. Completion can race abort | Frontend ignores later outputs for removed request. Existing client output persists; external tools are unrelated. No durable restart history in this in-memory abort path |
| vLLM HTTP disconnect | Chat handler uses cancellation wrapper; disconnect cancels handler, streaming response owns subsequent disconnect detection; generate catches CancelledError/GeneratorExit and aborts internal request [source I15][I15] / [source I18][I18] / [source I19][I19] | Async cooperative chain; connection closes before any durable receipt can be delivered | Proxy/disconnection detection delay and completion races; cannot classify accepted vs already terminal merely from caller disconnect | Partial text is incomplete; request cancellation does not stop application tools or shut down shared engine |
| vLLM global pause / shutdown | Administrator/owner targets entire engine: pause has `abort`, `wait`, `keep`; shutdown cleans owned background process/IPC [source I15][I15] | `wait` drains; `keep` retains queued work for resume; `abort` ends in-flight requests. These are materially different global operations | Broadcast effects and shared capacity make inappropriate per-attempt escalation unless engine is exclusively owned. Idempotence not a generic guarantee | Paused work can resume, so paused is not terminal. Shutdown cleanup is not app-tool/remote-effect settlement |
| Bedrock batch `StopModelInvocationJob` | Caller targets durable job ID/ARN, independent of original request/connection [source I20][I20] | HTTP 200 empty success; status API separately exposes `Stopping` vs `Stopped`, so retain response and poll exact job [source I21][I21] | Conflict/notfound/access/throttle errors distinguish rejection types. No explicit repeat-stop idempotence promise found; reconcile before retry after ambiguous delivery | Partial S3 output and already processed charges remain. Persist ARN/region and query after restart; job stop is not deletion/rollback [source I20][I20] / [source I21][I21] / [source I22][I22] |
| OpenAI Realtime `response.cancel` (additional distinct useful example) | Exact optional response ID, or absent ID means in-progress response of default conversation; optional client event ID [source I23][I23] | Server emits `response.done` with cancelled status; no active response yields error while session remains unaffected | Repeated delivery after terminal can error; not background-Responses idempotence. Untargeted delivery can hit later active work, so replay demands exclusivity/generation fencing | Session remains reusable. Audio-buffer clear is separate from generation cancellation; neither settles application-owned tools. No durable restart/replay guarantee supplied by this event contract [source I23][I23] |

Bedrock and Ollama's ordinary client-side tool loops execute functions in application code. Stop new tool admission and reconcile each already-started executor independently of model/HTTP cancellation. A Lambda invocation, database mutation or local subprocess does not stop merely because generation ceased. Bedrock server-side tools form a different effect-owning profile. Retain partial text and usage as observed; do not turn stream EOF, an abort exception or dropped connection into a validated final artifact. [Bedrock client tools][I7] / [Bedrock server tools][I8] / [Ollama tools][I12]

Source snapshots for local comparisons: Ollama JS `2b12fad6475c9f0e92a19793412293c9ecfaef18`, Ollama server `b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce`, vLLM `01549796563f2e8bd0d6b08243cfb954a7b42ec8`, OpenAI Python `e5de2e5656fb3d4fa70f050195382e6a4d59f806`. They are evidence snapshots, not dependencies adopted by this repository.

## 8. ACP v1 versus v2 draft

ACP source snapshot: `9e032156545412be9bba5e092f12d0080c499b6d` (2026-10-01); the v2 pages remain **draft**. Negotiate explicit profiles; package version numbers do not identify protocol generation.

| Mechanism | Target / initiator | Receipt and timing | Limits |
|---|---|---|---|
| ACP v1 `session/cancel` | Client→agent notification with sessionId; current prompt turn. | No response to cancellation notification. Original `session/prompt` returns stopReason=cancelled after agent reports ongoing operations aborted and pending updates flushed. | Stop model/tool invocations ASAP; accept trailing updates. Client must cancel outstanding permission asks. Optimistic client tool status is not execution evidence. Session remains conversationally reusable after turn. [source H12][H12] |
| ACP v2 draft `session/cancel` | Same current-session foreground work targeting, no exact turn/control-command ID. | Confirmation is idle state_update with stopReason=cancelled, not prompt response. | Prompt response acknowledges message insertion only. Foreground idle can coexist with background activity. Therefore cancelled state is not owner exit or all-effect settlement. Explicit v2 negotiation required. [source H13][H13] |
| ACP v1/v2 `$/cancel_request` | JSON-RPC request identity, either peer can initiate. | Original request returns ordinary/partial result or -32800; notification itself has no acknowledgement. | Support optional; recipient MAY cancel request and nested activities. Not substitute for session/prompt cancellation. Internal cancellation can produce same -32800. [source H14][H14] |
| ACP `session/close` | Active session identity, request-response. | Agent cancels ongoing work as session/cancel then frees session resources, returns empty object. | v1 capability gated; v2 required for session surface. Missing/inactive session may error; no universal idempotence. Separate from persisted-history deletion. No OS-descendant receipt is standardized. [source H15][H15] / [source H16][H16] |
| ACP v1 terminal/kill, terminal/wait_for_exit, terminal/release | Agent→client, sessionId + exact terminalId. | kill requests command termination; wait reports exitCode/signal; release invalidates ID and frees resources (killing still-running command). | Preserve final output before release. Distinct command termination and exit observation. No guaranteed arbitrary-descendant or remote-job settlement. These execution methods are removed from v2; its terminal surface is display-only. [source H17][H17] / [source H13][H13] |

ACP provides more than interchangeable framing: it standardizes the foreground cancellation lifecycle and expected observation path. That materially reduces adapter translation and gives common conformance fixtures. It does **not** standardize all effect/owner settlement, durable caller command deduplication, exact turn compare-and-cancel, or safe replay against a reused session. v2 explicitly separates foreground idle from background activity. Its session close releases session resources; it still is not an OS/remote-effect certificate. [v1 prompt lifecycle][H12] / [v2 lifecycle changes][H13] / [v2 close][H16]

A client must tolerate trailing updates during cancellation, settle pending permission exchanges, and keep cancellation intent distinct from response/state observation. Loading/resuming history or replaying updates cannot fabricate a missing cancellation receipt. With current-session targeting, exclusive attempt/session binding and inhibited successor work are the adapter's responsibility. ACP remains preferred-but-optional architecture under the existing conformance gate; no ACP migration is proposed by this review.

## 9. Why fewer generic outcomes are sufficient

Normalize enough to answer three deterministic questions: **what control did we try and what receipt exists; what is the target's observed outcome; what required ownership/effect scope is now settled?** “Already terminal” and “stale target” can be classified adapter outcomes without expanding the whole attempt state machine. “Unsupported” describes capability; “unknown” describes missing evidence and must not be folded into rejection.

Prefer retaining the existing methods with adapter-local mechanisms and explicit evidence over six new generic stop commands. If a future public API rename to `request_stop` improves clarity, it should preserve scope, policy and uncertainty rather than imply stronger behavior. A single Boolean advertised interruption capability is insufficient to select a force-stop strategy; preflight can initially record reviewed control profile/coverage in existing facts. Add a typed generic capability only when scheduling/admission actually branches on it.

Acceptance, generation/turn termination, owner exit and effect settlement remain orthogonal. This is required by Codex's completion race, vLLM's frontend-before-engine abort ordering, Claude's queued/background work and remote stored jobs. Keeping their mechanisms private avoids needless generic complexity; preserving their distinct evidence prevents unsafe retry or capacity release. Future schema additions are reversible only if old receipt meanings remain intact.


## 10. Process supervision and containment limits

A direct child, process group, session and process tree are different sets. A PID identifies a current process, not a durable generation. POSIX/macOS signal calls target a PID or group; success reports signal delivery eligibility, not confirmed exit. `waitpid` reports waitable child state. A process stopped by SIGSTOP can resume and is not terminal. `setsid()` creates a new session/group, allowing a descendant to leave a parent's kill group where permitted. Reparenting does not make it part of the original group again. [Apple kill][OS1] / [Apple wait][OS2] / [Apple setsid][OS3]

For the current owner, direct-child reaping + old process-group emptiness + bridge disconnect is useful evidence **within that verified scope**. It cannot prove the absence of a detached child, daemon handed work over IPC, provider computation or remote tool job. A process can also finish naturally while output pipes remain held by descendants. Supervisor status/receipts must bind generation, executable, attempt and coverage, not just a recycled PID. Never expand a signal to all user processes as a cleanup workaround. [Local owner implementation](../../src/orchestrator/backends/codex_owner.py) / [Python subprocess semantics][OS4]

TERM is a cooperative opportunity on POSIX; KILL prevents user-space cleanup. Neither undoes files/network effects already produced. Python `terminate()` targets the child; on Windows it uses `TerminateProcess`, unlike a POSIX graceful signal. Client task cancellation does not itself call either operation. Keep draining bounded output and waiting separate from requesting termination. [Python subprocess semantics][OS4] / [Python task cancellation][OS5]

Linux cgroup v2 provides a stronger membership boundary: `cgroup.kill` kills the group's subtree and handles concurrent fork/migration during that operation; `cgroup.events: populated=0` reports no live member processes. This still depends on correct admission/membership authority and does not settle a remote job or rollback effects. It is not available as a drop-in macOS facility. Windows Job Objects can include children and terminate members, but breakaway policy changes coverage; they too require scoped evidence. These are comparative options, not a recommendation to build new infrastructure in M6. [Kernel cgroup v2][OS6] / [Microsoft Job Objects][OS7]

**Descendant-containment acceptance:** if the admitted profile cannot exclude escape from the claimed ownership boundary, a receipt for an empty group cannot certify arbitrary descendant settlement. Narrow the claim or fail the required guarantee; do not make `settled=true` broader than its evidence. No containment subsystem was implemented or empirically certified here.

## 11. Bounded escalation and timeout policy

The useful sequence depends on ownership and risk, rather than on a universal “interrupt, TERM, KILL” recipe:

| Profile | Appropriate candidate sequence | Unsafe or meaningless escalation |
|---|---|---|
| Dedicated local harness | Freeze new work; narrow cancel; bounded drain/observe; if preauthorized, terminate exact exclusive owner; independently inspect scope | Retargeting another turn, killing shared service, treating group exit as remote settlement |
| Shared local inference service | Cancel/abort exact request; stop app dispatch/tools separately; reconcile request | Killing the whole daemon/GPU engine to stop one worker; all tenants are affected |
| Stateless remote stream | Stop application tool admission; close/cancel request with documented semantics; retain uncertainty about remote work | Killing local HTTP client as proof of provider cancellation; replaying request to discover outcome |
| Stored response/remote job | Cancel exact durable ID; poll authoritative status within budget; reconcile after restart | Local process death as job termination; discarding response/job ID; assuming idempotence without contract |
| Application-owned tool loop | Cancel generation and each tracked tool executor under its own policy; await/fence effects | Generation token alone as a tool/process-tree stop; cancellation handler that launches replacement work |

Escalation after rejected/uncertain cancel may be justified for an exclusively owned local worker when the user intent is stop and the policy permits termination. Record it as a **different action**, with its own target, authorization, deadline and result. It must not manufacture provider acceptance. If the original turn finished naturally, preserve that outcome and apply the stop intent to prevent further work. A cleanup receipt cannot decide whether incomplete artifacts satisfy the workflow.

Revocation can restrict future tool calls/leases/network access when an independent enforcer actually mediates them. It may not revoke cached credentials, already dispatched remote work or irreversible effects. It can also remove the channel needed to observe settlement; capture required evidence before destroying it where safe. Human action is appropriate when only broader shared-resource termination would stop work.

Distinguish execution deadline, cancellation-response deadline, graceful-drain deadline and owner-settlement deadline. Expiry triggers policy action and attribution; it does not prove cancellation. `asyncio` cancellation is cooperative and may be suppressed; a timed-out wait may already have sent an RPC. A known, settled attempt can be classified timed-out because its policy deadline caused stopping, while retaining the actual provider outcome. Otherwise retain unknown and capacity. [Python task cancellation][OS5] / [current coordinator](../../src/orchestrator/execution/coordinator.py)

## 12. Persistence, deterministic authority and restart

**Inference chooses; deterministic code validates and executes.** No model decides that a process is dead, a reservation may be released or an uncertain control is safe to retry. Persist policy and intent before external delivery, then append receipts/observations without overwriting earlier uncertainty as if it never existed.

| Moment | Minimum durable information |
|---|---|
| Before control delivery | Command/action IDs, actor, stop/deadline intent, expected run revision, attempt + exact target/owner generation, admitted profile/policy, allowed escalation and deadline; commit state/events/outbox together |
| At delivery attempt | Claim/time, selected mechanism and bound target, preventing blind replay after a crash |
| Upon response | Correlated ACK/rejection/unsupported or unknown; sanitized code/reason and receipt evidence; retain it before later cleanup when available |
| Before each distinct escalation | Linked action identity, exact resource target and authorization; do not hide force termination inside a fictional provider ACK |
| Upon observations | Exact terminal status, process/descendant/effect evidence and scope, partial artifact references; preserve observations independently of ACK |
| On final decision | Classified outcome, validated artifacts, remaining gaps and retry policy; release reservations in the same durable transition only when required ownership/effect conditions hold |

Existing interventions, action IDs, outbox claims, lifecycle events, preflight facts, artifact storage and owner receipts already provide most of this. For immediate M6 diagnostics/response-shape repair, use these existing facilities; no new generic operation table or physical SQLite migration is justified. Do not backfill control receipts from history.

There is a concrete **semantic** gap if implementing general multi-phase stop: the current durable delivery status collapses accepted cancellation with subsequent cleanup and has no typed settlement scope or escalation phase. Preserve receipt phases first using existing attributable events/evidence. If deterministic recovery must branch on independent acceptance/termination evidence, propose a small versioned typed receipt/event addition, preserve old meanings and add crash fixtures; free-text `detail` is inadequate for those decisions. Storage can often remain the existing JSON/event tables, but a persisted contract change still needs explicit review and compatibility tests. This research does not authorize it or a CAND-005 tool-operation ledger.

On restart, claimed-but-unanswered delivery is unknown. Query exact durable response/job identity or original owner evidence; use historical session state only for what its source guarantees. Do not resend an active-session cancel against a newly active successor. A remote API with documented idempotent ID cancellation may permit policy-controlled repeat delivery; a generic command UUID is not automatically an upstream idempotency key. Safely stopping the local owner does not by itself make retry safe: completed writes or remote work may require deduplication/compensation outside this scope.

## 13. Failure and recovery cases

| Case | Facts to retain | Safe deterministic progression |
|---|---|---|
| Request lost / no reply | Delivery attempted; no ACK | Unknown unless authoritative no-delivery evidence; inspect, no blind replay |
| Accepted, response lost | Same local evidence as lost request | Reconcile target/effects; later terminal does not invent ACK |
| Stale target | Exact rejection/code and original target | Never silently retarget; inspect original, preserve successor |
| Already terminal | Terminal evidence and any separate control rejection/success | Preserve real outcome; settle resources; no cancellation credit |
| Process dies before ACK | Exact death evidence, delivery unknown | Scope/effects still need checking; no fabricated provider acceptance |
| Provider rejects, operation later stops | Rejection plus later observed stop/cause if known | May resolve execution/settlement with evidence; rejection remains; M6's stricter current policy remains until approval |
| Provider accepts, work continues | Accepted receipt, live activity/coverage | Bounded wait/escalation per policy; retain capacity; no immediate terminal transition |
| Service crashes during cancellation | Durable intent and last committed phase | Reconcile owner/target; uncommitted observations cannot be invented; do not rerun launch |
| Owner exits, detached child survives | Child exit but incomplete descendant scope | Unknown/unsettled; group-only evidence insufficient |
| Remote tool/job continues | Local cancellation and remote active/unknown state | Keep required effect accounting/reservations; cancel/reconcile remote ID if supported |
| History says interrupted, no receipt | Historical status plus observer identity | No retroactive ACK; fresh-reader synthetic status is especially weak; respect M6 unknown policy |
| Duplicate delivery | Original command, target and phase | Local dedup only within its durability; repeat upstream solely with proven idempotence and stable target |
| Cancel races with normal completion | Both control result and terminal result | Keep completion if validated; exact-cancel test inconclusive, not cancelled by fiat |
| Queued/background work restarts | Current foreground stops; successor or background remains | Stop admission/cancel queue only within approved scope; session idle is not whole-worker quiescence |
| Partial output/tool effects | Retained bytes/tool receipts, missing final contract | Preserve failed evidence; no successful artifact promotion or automatic effect replay |

## 14. Smallest M6 correction and decision boundary

Recommend a separately authorized, bounded correction before more live interrupt acceptance runs:

1. Replace the synthetic echoed-turn response assumption with the real pinned response model; correlate the RPC through the SDK's request ID and the already-bound exact target. Keep provider terminal status and owner settlement separate.
2. Preserve sanitized `InvalidRequestError` code/message and target/owner/timing evidence so no-active-turn, mismatched-active-turn, thread-not-loaded and submission failures can be distinguished. Do not claim which caused the historical rejection without its retained evidence.
3. Add offline cases for empty success + interrupted terminal, empty success + normal completion, stale/no-active target, response loss, duplicate command, rejected request followed by stop, close failure after known ACK, restart between phases and sibling/session protection. Correct the fake to match actual SDK shapes.
4. Keep exact-turn M6 targeting. Do not copy TUI active-turn retry, send a blank turn ID, upgrade the runtime, migrate ACP or label forced termination as passing the exact interrupt test.
5. Before adopting force-stop fallback, obtain approval for its policy/evidence semantics. Verify exclusive ownership and descendant containment; preserve rejected/unknown provider control plus separate termination evidence. No new containment subsystem is authorized by this report.

**Generic persisted change now:** not needed for the pinned response/diagnostic correction. **For richer stop semantics later:** a small additive, versioned receipt/event contract may be warranted when the coordinator needs independent cancellation/termination/effect facts to release capacity after fallback. That requires a concrete implementation proposal and crash tests, not a universal cancellation ontology.

**Decision deadline:** resolve the response/receipt mismatch before claiming M6 live interrupt acceptance; decide force-stop policy and ownership coverage before broadening stop guarantees or adding a second runtime. Do not let this research advance M6 to M7. Message/API renaming and adapter mapping are reversible; false persisted ACKs, released unknown effects and untraceable retargeting are not. CAND-005 remains unresolved; ACP adoption, all new runtimes, UI and Task 07 remain out of scope.

## 15. Evidence register and validation limits

Primary sources below distinguish pinned implementation from rolling documentation/draft protocol. Missing explicit idempotency, descendant or remote-effect guarantees are recorded as unproven rather than inferred. A source-level cancel implementation does not certify a deployed host, provider billing cutoff or every plugin/tool. Source inspection and the one offline response-model probe made no inference requests, opened no app-server and changed no credentials.

The offline probe of installed `openai-codex==0.159.2` constructed `TurnInterruptResponse` from `{}` and returned `{}` with no `turn_id`; this validates the model mismatch only. No live rejection was reproduced. Report validation passed local/reference-link, structure and whitespace checks. Existing source, canonical documents and historical tasks matched their pre-review hashes. An unrelated `.codex/config.toml` change appeared during the review and was left intact; the isolated candidate backlog was excluded from inspection. No source/test suite is claimed newly passed by this documentation-only review.

| Source group | Scope and evidence level |
|---|---|
| C1–C25 | Codex source pinned to 0.159.2: SDK/schema, turn validation/terminal handlers, frontend policies, owner/task/history paths and process-group helpers. Source-level evidence; no live control reproduction. |
| H1–H6 | Pinned Claude Python SDK plus rolling official Claude Code/TypeScript docs; runtime feature-version requirements remain explicit. |
| H7–H11, H18 | Pinned OpenCode HTTP/session runner/background registry and SDK process helpers. |
| H12–H17 | ACP v1 normative pages and v2 draft as inspected 2026-10-02; do not merge their lifecycle contracts. |
| H19–H22 | Official Claude Managed Agents event, scope, CLI and session-operation docs; distinct remote profile. |
| I1–I3, I6–I8, I20–I22 | Official AWS inference/Responses/tool/batch-job API and user documentation; endpoint differences retained. |
| I4–I5, I23 | Official OpenAI synchronous/background/Realtime control docs and pinned Python stream source. |
| I9–I14 | Ollama official JS/API/tool docs and pinned client/server/runner source. |
| I15–I19 | Pinned vLLM frontend/output/engine/HTTP cancellation source; ordering evidence, not host certification. |
| OS1–OS7 | Apple system-call manuals, Python documentation, Linux kernel and Microsoft supervision documentation. |

Reference links are attached to the claims above. The [Ollama iterator implementation](https://github.com/ollama/ollama-js/blob/2b12fad6475c9f0e92a19793412293c9ecfaef18/src/utils.ts#L27), [Codex aborted-event handler](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/bespoke_event_handling.rs#L1204) and [ACP source snapshot](https://github.com/agentclientprotocol/agent-client-protocol/commit/9e032156545412be9bba5e092f12d0080c499b6d) supplement the grouped references.


[OS1]: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/kill.2.html
[OS2]: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/wait.2.html
[OS3]: https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/setsid.2.html
[OS4]: https://docs.python.org/3/library/asyncio-subprocess.html
[OS5]: https://docs.python.org/3/library/asyncio-task.html#task-cancellation
[OS6]: https://docs.kernel.org/admin-guide/cgroup-v2.html
[OS7]: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects

[H1]: https://github.com/anthropics/claude-agent-sdk-python/blob/bfb895c6ef46e095191938b4eda798a025957c09/src/claude_agent_sdk/client.py#L308
[H2]: https://github.com/anthropics/claude-agent-sdk-python/blob/bfb895c6ef46e095191938b4eda798a025957c09/src/claude_agent_sdk/_internal/query.py#L706
[H3]: https://code.claude.com/docs/en/agent-sdk/typescript#sdkcontrolinterruptresponse
[H4]: https://code.claude.com/docs/en/agent-sdk/python#example---using-interrupts
[H5]: https://github.com/anthropics/claude-agent-sdk-python/blob/bfb895c6ef46e095191938b4eda798a025957c09/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L962
[H6]: https://code.claude.com/docs/en/interactive-mode#general-controls
[H7]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/server/routes/instance/httpapi/handlers/session.ts#L232
[H8]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/session/run-state.ts#L78
[H9]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/effect/runner.ts#L197
[H10]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/sdk/js/src/server.ts#L95
[H11]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/sdk/js/src/process.ts
[H12]: https://agentclientprotocol.com/protocol/v1/prompt-turn#cancellation
[H13]: https://agentclientprotocol.com/protocol/v2/migration#the-new-prompt-lifecycle
[H14]: https://agentclientprotocol.com/protocol/v1/cancellation
[H15]: https://agentclientprotocol.com/protocol/v1/session-setup#closing-active-sessions
[H16]: https://agentclientprotocol.com/protocol/v2/session-setup#closing-active-sessions
[H17]: https://agentclientprotocol.com/protocol/v1/terminals
[H18]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/core/src/background-job.ts#L113
[H19]: https://platform.claude.com/docs/en/managed-agents/events-and-streaming
[H20]: https://platform.claude.com/docs/en/api/typescript/beta/sessions/events
[H21]: https://platform.claude.com/docs/en/cli-sdks-libraries/cli/sessions-connect
[H22]: https://platform.claude.com/docs/en/managed-agents/session-operations
[I1]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_ConverseStream.html
[I2]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_InvokeModelWithResponseStream.html
[I3]: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
[I4]: https://developers.openai.com/api/docs/guides/background
[I5]: https://github.com/openai/openai-python/blob/e5de2e5656fb3d4fa70f050195382e6a4d59f806/src/openai/_streaming.py#L130
[I6]: https://docs.aws.amazon.com/bedrock/latest/userguide/bedrock-mantle.html
[I7]: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html
[I8]: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-server-side.html
[I9]: https://github.com/ollama/ollama-js#abort
[I10]: https://github.com/ollama/ollama-js/blob/2b12fad6475c9f0e92a19793412293c9ecfaef18/src/browser.ts#L58
[I11]: https://docs.ollama.com/api/generate
[I12]: https://docs.ollama.com/capabilities/tool-calling
[I13]: https://github.com/ollama/ollama/blob/b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce/server/routes.go#L692
[I14]: https://github.com/ollama/ollama/blob/b0c1ca4f7549d7acdfa52a7dcffc934bc63a43ce/llm/llama_server.go#L1735
[I15]: https://github.com/vllm-project/vllm/blob/01549796563f2e8bd0d6b08243cfb954a7b42ec8/vllm/v1/engine/async_llm.py#L876
[I16]: https://github.com/vllm-project/vllm/blob/01549796563f2e8bd0d6b08243cfb954a7b42ec8/vllm/v1/engine/output_processor.py#L523
[I17]: https://github.com/vllm-project/vllm/blob/01549796563f2e8bd0d6b08243cfb954a7b42ec8/vllm/v1/engine/core_client.py#L1281
[I18]: https://github.com/vllm-project/vllm/blob/01549796563f2e8bd0d6b08243cfb954a7b42ec8/vllm/entrypoints/serve/utils/api_utils.py#L51
[I19]: https://github.com/vllm-project/vllm/blob/01549796563f2e8bd0d6b08243cfb954a7b42ec8/vllm/entrypoints/openai/chat_completion/api_router.py#L56
[I20]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_StopModelInvocationJob.html
[I21]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_GetModelInvocationJob.html
[I22]: https://docs.aws.amazon.com/bedrock/latest/userguide/batch-inference-stop.html
[I23]: https://developers.openai.com/api/reference/resources/realtime/client-events#response-cancel
[C1]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/turn_processor.rs#L1598
[C2]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py#L701
[C3]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/async_client.py#L328
[C4]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server-protocol/src/protocol/v2/turn.rs#L327
[C5]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/tests/suite/v2/turn_interrupt.rs#L35
[C6]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/command_exec.rs#L355
[C7]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_processor.rs#L2434
[C8]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_processor.rs#L1020
[C9]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_processor.rs#L1709
[C10]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py#L283
[C11]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/lib.rs#L209
[C12]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/bespoke_event_handling.rs#L185
[C13]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/bespoke_event_handling.rs#L1563
[C14]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/session/mod.rs#L5049
[C15]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_lifecycle.rs#L416
[C16]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/tui/src/app/thread_routing.rs#L660
[C17]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/exec/src/lib.rs#L1226
[C18]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/session/handlers.rs#L287
[C19]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/tasks/mod.rs#L920
[C20]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/tasks/mod.rs#L536
[C21]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/utils/pty/src/process_group.rs#L1
[C22]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/utils/pty/src/child_command.rs#L300
[C23]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/unified_exec/process.rs#L246
[C24]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_processor.rs#L5811
[C25]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/src/session/turn.rs#L2599
