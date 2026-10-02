# Cross-runtime authority and interoperability review

**Date:** 2026-10-02. **Baseline:** `c55c20a8d43734e49ee6762b58d74dc5f60c5c14`, branch `codex/research`, with existing unrelated working changes preserved. **Status:** eight architecture decisions approved and promoted on 2026-10-02; supporting research, not a canonical contract or implementation task. See [canonical admission](../IMPLEMENTATION_PLAN.md#authority-oriented-runtime-admission), [ACP adoption gate](../IMPLEMENTATION_PLAN.md#acp-interoperability-and-adoption-gate) and [M6 corrective Task 06b](../../tasks/06b-cross-runtime-authority-policy.md). The review below retains its original findings and proposal wording; implementation and ACP adoption are not claimed.

Reviewed the canonical implementation plan, integration audit, M6 task/review, current backend/preflight/owner models, coordinator admission and captured configuration fixtures. Per the user's clarification, the research intake backlog was neither accessed nor updated. No source, canonical plan, runtime configuration or Task 07 changes; no live inference or runtime installation.

## Recommendation

**Adopt the proposed direction with an essential qualification: closed-world authority and required correctness guarantees; tolerant ingestion of demonstrably non-authority observations and behavior.** Semantic labels alone cannot prove harmlessness. An unknown setting is tolerable only when its consumer is known to be observational, or an independently enforced boundary contains every reachable effect and preserves required semantics. Unknown executable configuration in an opaque harness remains a rejection.

The smallest correction is adapter-local: replace exact equality for reviewed noncritical fields with semantic validators, narrow the feature inventory to an authority/compatibility evidence input, and separate admission-critical drift from forensic configuration drift. Keep the runtime pin, immutable receipts, permission ceilings, output validation and settlement rules. No generic persisted schema migration is needed for this M6 correction. A shared vocabulary/evaluator can be introduced without mirroring provider flags in the coordinator.

ACP can be a preferred interoperability protocol for qualifying harnesses behind `WorkerBackend`, while our admission/policy layer stays authoritative. It does not, by itself, make a harness conformant. The inspected Codex ACP adapter is not a drop-in replacement for M6's guarantees; the detailed comparison below identifies the checks it transfers and those it cannot remove.

## What the current implementation actually does

- [`_ReviewedRuntimeSetting`](../../src/orchestrator/backends/codex_backend.py) stores `classification`, but `_configuration_issues` does not consult it. It checks expected values/types and rejects unknown keys in effective configuration **and each layer**, even when false/empty. `required`, `allowed_optional`, `forbidden` and `inert_metadata` mix presence policy with semantic risk.
- A local, provider-free invocation reproduced: baseline accepted; changing `file_opener` from `vscode` to `none` rejected; an unknown top-level `false` rejected; an unknown feature `false` rejected. These demonstrate current behavior, not proof that either unknown is safe.
- `start()` also requires the entire sanitized configuration/layer hash to match preflight. Merely relaxing `_configuration_issues` would still reject harmless drift at this second gate.
- The integration audit describes feature-registry classes, but in this checkout the feature-list text is a fixture/inventory. Its test checks a few captured lines; no executable feature-registry classifier was found in `src/`. The running gate is the config/read rule table. Treat the audit's registry policy as a statement to reconcile, not an implemented security guarantee.
- [`BackendPreflightSnapshot` / `PreflightFact`](../../src/orchestrator/domain/backend.py) already provide versioned fact collections, state, reason and evidence references. The coordinator validates preparation/owner identity and persists the record; provider-setting interpretation currently resides in the adapter. The scalar fact schema is sufficient for a bounded versioned authority summary, but a non-null value labeled `verified` is not automatically evidence of enforcement.

The latest audit records a read-only live smoke pass and unresolved exact-turn interruption. The canonical plan's earlier status still says live compatibility is unverified. This review does not resolve that discrepancy or rerun live tests; neither status justifies relaxing policy or claiming settled external effects.

## Runtime comparison

“Owns” below means executes/manages the resource; enforcement may belong to another component. `cwd` is context unless an actual boundary restricts access.

| Runtime/profile | Filesystem, workspace, shell/process | Network, tools, credentials | Enforcement and capability evidence | Lifecycle and unverifiable areas |
|---|---|---|---|---|
| **Codex SDK/harness**, project pin 0.159.2 | Harness executes local tools; service owns workspace selection; adapter owns its process group | Shell network, model/auth traffic, web, apps/MCP and browser surfaces are separate. Harness owns login and internal tools | Configured and partly reported; exact binary/source, effective settings and enforcement coverage are needed. Shell sandbox does not establish all-surface containment [Codex security and network coverage][O1] / [Codex configuration: telemetry, history and related settings][O2] / [Pinned feature registry and consumer descriptions][O3] | Thread/turn history is distinct from process ownership; SDK close and a saved terminal view do not prove descendants settled [Pinned SDK environment, initialization and close][O4] / [Pinned history status handling][O5] |
| **Claude Agent SDK / Claude Code** | Harness owns built-in tools; Bash sandbox covers commands/children, while built-in file/web tools and hooks/MCP/LSP/helpers have separate boundaries | Credentials/environment and configured plugins/hooks can expose host or remote authority. Tool auto-approval is distinct from inventory | SDK config/permissions plus managed settings and OS isolation. `allowed_tools` auto-approves; earlier approvals can bypass `canUseTool` [Claude sandbox scope][C1] / [Claude SDK permissions][C2] / [Claude secure deployment][C3] | Interrupt requires draining buffered results; direct-child cleanup effort is not detached-descendant or remote-effect settlement [Claude interruption][C4] |
| **Bedrock Converse / ConverseStream**, client-side tool use | Application executor owns workspace, filesystem and shell; model returns proposed tool calls | AWS IAM authorizes inference; app/tools own their own principals and egress. Tool schemas do not grant host permissions | App dispatch/policy and OS controls enforce tools; IAM enforces service access. Sampling is behavior, tool execution is a separate authority path [Bedrock client-side tool execution][B1] / [Bedrock Converse API/IAM/configuration][B2] | Generation stop is not tool completion. Converse has no documented stored-response lookup/cancel contract equivalent to stored Responses APIs [Converse streaming events][B3] |
| **Ollama chat**, local model or explicitly selected cloud model | Inference daemon owns model storage/process; app executes proposed functions and owns workspace | Localhost can route an authenticated cloud-model request. Server startup identity, bind address and cloud policy matter separately from app tools | Tool dispatch enforced by app; daemon constrained by its host. Cloud-disable configuration does not replace OS egress control [Ollama tool calling][L1] / [Ollama local/cloud authentication][L2] / [Ollama server, storage and cloud configuration][L3] | `done` ends a response, not app tools or the daemon. Reviewed API gives no durable attempt-level settlement receipt [Ollama chat response semantics][L4] |
| **vLLM server** | Host owns inference process; media path grants and trusted model/plugin code can access server resources; app executes tool calls | Startup plugins, remote-code trust, media fetching, server/control endpoints and credentials are authority surfaces | Deployment/OS/network controls plus startup configuration; request schema alone cannot attest containment. API-key coverage is not universal [vLLM engine authority-bearing startup arguments][V1] / [vLLM security: plugins, network, API-key and media limits][V2] / [vLLM tool-call output][V3] | A shared server need not exit per request. Request completion cannot settle separate app executors or unknown extension effects |
| **ACP v1**, protocol-mediated harness | Client may supply filesystem/terminal execution; agent may retain its own tools. Service must enforce callback scope | Agent handles auth and connects/launches MCP from client-supplied configuration; v1 terminal requests execute at the client. Both carry process/network/principal authority | Negotiated support identifies callable methods. Permission requests are optional agent behavior, not universal interposition [ACP v1 initialization/capabilities][A1] / [ACP v1 filesystem][A2] / [ACP permission requests][A3] | Prompt cancellation has protocol receipt semantics, while OS/external settlement remains owner-specific. Draft v2 changes these semantics [ACP v1 prompt/cancellation][A4] / [Draft ACP v2 migration, ownership and receipt changes][A5] |
| **OpenCode** | Harness tools run with host authority; service owns chosen cwd/workspace but cwd is no sandbox | Plugins get shell/SDK access, may replace built-ins, inject environment and connect MCP/OAuth tools | Project's security model explicitly disclaims sandboxing; permissions are user-awareness controls. Outer isolation is needed for a hard ceiling [OpenCode pinned security boundary][P1] / [OpenCode plugin shell access, environment and replacement tools][P2] / [OpenCode configuration precedence][P3] | Session abort/server stop differ; SDK stop request is not awaited process-tree settlement. Persisted sessions do not establish live ownership [Pinned SDK server][P4] |

Direct-model APIs have a smaller *model-to-tool* trust surface because the app can reject every proposed effect before dispatch. Their inference endpoint still has data-access, routing, credentials and resource implications. Local inference moves that endpoint onto a host we may control; it does not automatically sandbox the server, plugins, media fetches or application tools. Bedrock Agents/AgentCore and provider-hosted execution tools are separate profiles, not covered by the Converse conclusion.

## Smallest normalized authority model

Use a small set of effect dimensions with scope and enforcement evidence, rather than one Boolean per provider feature:

| Dimension | Minimum normalized meaning |
|---|---|
| Filesystem/data | Read, write, create/delete; allowed roots/resources, exclusions, runtime-state versus deliverable storage, disclosure/retention limits |
| Process/executable | Shell/code execution, executable/plugin identity, background children, local service/IPC/device access, permitted descendants |
| Network/remote services | Actor and purpose: inference/auth, tool egress, telemetry, listener/control ingress; destination/scope and enforcing layer |
| External tools/delegation | Approved tool implementation/server identities, delegated operation scope, nested agents and ceilings that descendants inherit |
| Principal/auth material | Which process/tool can use an identity, read auth material or call a broker; secret references/scopes only, never credential values |
| Durable/autonomous effects | Persistent stores, remote mutations/jobs, startup hooks and work that may continue after a turn; owner and reconciliation obligations |

Attach **workspace/resource identity**, **executor**, **permission enforcer**, **lifecycle owner**, **required guarantee**, **evidence/provenance**, and **coverage gaps** to each relevant dimension. Approval is an authorization mechanism, not a substitute for these scopes. Lifecycle controls and artifact/identity/budget correctness are separate required guarantees; disabling authority does not make malformed completion evidence acceptable.

Admission asks whether reachable effects are bounded by the resolved ceiling **and** required guarantees are established. Available authority may exceed what the task requests only if enforcement makes the excess unreachable. For an opaque harness, record its owner, observed claims, independently enforced limits and unknown coverage. Unknown coverage intersecting a mandatory restriction rejects that profile; opacity is never an implied waiver.

Keep these concepts distinct:

| Fact | Meaning |
|---|---|
| Present | A key/field exists |
| Enabled | A toggle resolved active for a component; other gates may still block it |
| Available | An operation is exposed/supported |
| Permitted | The resolved policy grants this action/scope |
| Enforced | A named mechanism prevents actions outside that grant, within stated coverage |
| Observed | Evidence from a read/probe/event; absence of observed effects is not absence of authority |
| Authority-widening | A change makes additional effects/resources/principals reachable beyond the accepted grant |

## Classification: useful summaries, insufficient security rules

Retain A/B/C as reporting labels, with a separate set of dependencies such as authority, lifecycle, identity, output, budget and provenance. A field can affect more than one. Presence requirements, value validators and evidence requirements must be separate from its category.

| Class | Operational rule | Counterexamples to broad exemptions |
|---|---|---|
| **A: authority/effect-bearing** | Compile to granted scope, verify enforcement, reject unsupported/unverified excess | Read-only still exposes data; a proxy toggle may enable enforcement rather than widen authority; changing tool implementation under the same name changes trust |
| **B: behavior within established authority** | Record/tolerate unless a required correctness/budget/provenance guarantee depends on it | Compaction algorithms can be B while compaction hooks execute code; retry settings can violate deadlines; cache retention and cached approvals have data/authority effects |
| **C: observational only** | Bound/sanitize and tolerate when the consumer cannot affect authority or required semantics | An inert label differs from an exporter endpoint/helper. Version/status/identity fields can be compatibility/lifecycle-critical despite looking like metadata |

Concrete checks against the proposed examples:

- **Telemetry:** Codex exporters can send prompts to configured endpoints; Claude telemetry helpers execute commands. Those settings are A. A bounded returned counter or display label can be C under an already accepted output policy. [Codex configuration: telemetry, history and related settings][O2] / [Claude telemetry and executable header helper][C5]
- **Compaction/caching:** OpenCode compaction invokes plugin code, and cached approvals change future authorization. A pure summarization choice remains B only within established data/compute limits; hook installation and approval cache scope do not. [Pinned compaction plugin path][P5]
- **Current “inert” rules need re-review:** `network_proxy` changes enforcement; `windows_sandbox_service` concerns containment; `history` concerns retention and may affect required recovery evidence; `project_root_markers` can affect configuration discovery. Instruction inclusion is behavior/provenance, not inert display. No automatic exemption should follow from today's labels.
- **Registry lifecycle tags:** the pinned Codex registry distinguishes a removed no-op flag from a deprecated flag. Some removed flags accompany behavior that is now always on; accepting the flag is not proof the corresponding tool is absent. Desktop requirements-only gates are not automatically reachable app-server features. Assess consumers and dependencies. [Pinned feature registry and consumer descriptions][O3]
- **Protocol metadata:** ACP extension metadata can advertise capabilities. Unknown informational notifications may be ignored; unknown authority-bearing requests must not gain dispatch rights. Closed lifecycle discriminators cannot be guessed. [ACP v1 extensibility][A6]

### What unknowns may be tolerated?

An adapter cannot establish harmlessness from an unfamiliar name, a `false` value, an SDK accepting extra fields, a successful smoke test or a provider's unscoped capability claim. Use one of two evidence routes:

1. **Known consumer contract:** a pinned schema/implementation demonstrates the field is ignored or only rendered/stored with bounded, sanitized handling, without forwarding it into executable configuration, routing or required decisions.
2. **Complete mediation:** an independently controlled execution boundary restricts all reachable effects to the accepted grant even if the behavior is unknown. Include hooks, plugin loaders, helper processes, credentials, control-plane endpoints, IPC and remote effects. A shell-only sandbox is insufficient for this inference.

No evidence route means reject the affected launch/control/configuration path. This does not require aborting a turn for an unrelated extra progress field. Fail closed for unknown authority changes, malformed policy/scopes, changed executable/principal identities, unsupported required controls, unknown terminal outcomes and unsettled effects. Tolerate reviewed display/format changes and unknown observational fields only under the above constraints. An unknown disabled-looking feature in executable configuration remains unresolved until disabled semantics or independent containment are established.

## Smallest correction before continuing M6

**Proposed; no correction implemented here.**

1. Make `_ReviewedRuntimeSetting.classification` operational only after replacing its mixed categories with semantic/dependency information and separate presence/value rules. Reclassify existing “inert” entries; do not add `if inert: allow anything`.
2. Keep exact checks for the SDK/runtime trust profile, deny-all escalation, verified sandbox/network/integration/delegation restrictions, model/effort/output contracts and process settlement. Use ranges/types/ignored-consumer evidence for specifically reviewed harmless fields. Evaluate effective restrictions and startup side effects; an overridden layer may still have caused plugin initialization.
3. **Narrow the registry allowlist's role.** Retain the inventory/version fixture for change detection and authority-path discovery; replace exhaustive feature-name/value admission with a bounded map of authority and required-semantic consumers. Known unavailable/no-op components can be accepted on pinned evidence. Keep unclassified executable paths closed. This reduces review cost by surface, not by declaring every unknown harmless.
4. Define an adapter-local authority/guarantee projection and versioned policy-profile ID. Add these as sanitized facts/evidence references in existing preflight groups. Record observed availability separately from enforcement assurance; do not manufacture verified enforcement from a non-null value.
5. Preserve the full sanitized configuration hash for forensic provenance; gate submission on the authority/required-semantics projection plus executable/config-source identity. Record tolerated noncritical drift as an event/diagnostic without rewriting the frozen snapshot. Unknown/new sources or changed authority still reject. Without this split, a tolerant config parser leaves the full-hash rejection intact.
6. Validate the correction with paired fixtures: benign display change accepted; unknown effectful feature rejected; same tool name/new implementation rejected; inherited hook blocked before initialization; ineffective sandbox/egress settings rejected; B/C change that breaks result identity, budget or recovery rejected; extra informational event accepted; projection drift rejected; repeated inspection never broadens authority. Keep current lifecycle regressions unchanged.

**Persistence decision:** no physical schema change is necessary now. Existing v1 snapshots can carry a projection revision/digest, policy-profile identity and evidence references through their fact groups. Define and test their semantics; generic string facts alone do not enforce policy. Preserve historical interpretations and require the new evidence only for new profiles/attempts. Before a second real backend requires richer resource scopes, assess a typed additive representation; do not preemptively design a universal tool ontology or migrate old snapshots.

**Deadline/reversibility:** approve the bounded policy correction before expanding M6 live activation; retain current fail-closed behavior until then. Mapping and classifier changes are reversible behind a versioned adapter profile. Mislabeling historic authority or losing effect/owner evidence is much harder to repair. ACP adoption is a separate reversible transport choice with its own conformance work, not a prerequisite to this correction.

## Added target: can ACP be the primary harness interoperability boundary?

**Yes, for admitted harness profiles; recommend it as the preferred common protocol when adding multiple harnesses. Keep the current M6 transport until a separately approved compatibility prototype meets the same guarantees.** The layering would be coordinator/ledger → provider-neutral `WorkerBackend` and authority admission → ACP session/progress/control mapping → a pinned harness profile and its actual enforcing owners. Direct-model APIs still belong behind their own runtime path; forcing them through ACP adds no necessary authority guarantee.

An “atomic execution unit” should mean one bounded attempt with atomic local admission/reservation/dispatch intent and attributable results. Its writes, network calls and child processes are not an atomic transaction. ACP supplies no general exactly-once launch, rollback or safe-retry guarantee. Use a fresh attempt/session, bounded budgets, exact correlation and independently settled ownership; unknown outcomes still retain reservations.

Our policy remains operationally authoritative only if every reachable effect is constrained by either our handlers or a reviewed enforcing runtime/outer boundary. Declining ACP permission callbacks is insufficient when agents can execute tools without those callbacks. ACP can advertise support and transport requests; it cannot certify that all effects traverse our service. An optional profile-specific evidence extension or local supervisor may provide the missing proof, but a missing extension must fail the required guarantee rather than trigger permissive fallback. [ACP v1 initialization/capabilities][A1] / [ACP v1 filesystem][A2] / [ACP permission requests][A3] / [ACP v1 prompt/cancellation][A4]

**Version caveat:** published ACP v1 offers client filesystem/terminal methods. The current **draft v2** removes those methods in favor of MCP-provided client tools and agent-owned terminal display; completion/cancellation moves to state-update semantics. Negotiate and test explicit profiles. Do not mistake an adapter package's version 2.x for ACP protocol version 2. [Draft ACP v2 migration, ownership and receipt changes][A5]

### Actual Codex-over-ACP evidence

Inspected the successor project `agentclientprotocol/codex-acp` at commit `68d7d2d5ddfc0ed5746f9f6130892dda685e65dd` (2026-10-01): package **2.1.1**, ACP SDK dependency **^1.5.0**, Codex dependency **^0.159.1**. These ranges are not M6's exact binary pin. It translates ACP to a Codex app-server subprocess; transport inherits its environment unless replaced. [Codex ACP pinned dependency manifest][X1] / [Codex ACP app-server transport][X2]

The inspected implementation enables experimental APIs and disables its request-attestation option; read-only mode maps to `on-request`, while default agent mode uses `auto_review`. Configuration marks session roots trusted and preserves ambient MCP names. Therefore neither a mode label nor an empty ACP MCP list proves M6's restrictions. No production client filesystem/terminal delegation calls were found in this adapter: Codex still executes those tools. [Codex ACP initialize options][X3] / [Codex ACP approval/sandbox mode mapping][X4] / [Codex ACP effective configuration/MCP construction][X5] / [Codex ACP advertised support][X6]

Its steering extension can inject input **or start a new turn** and gives no consumed-result revision guarantee. Shutdown requests termination without our independent descendant receipt. Its changed-file extension explicitly reports incomplete coverage. These are incompatible with assuming ACP itself supplies M6's control, cleanup or artifact guarantees. [Codex ACP steering extension][X7] / [Codex ACP exit/termination handling][X8] / [Codex ACP extension evidence limits][X9]

### Which M6 checks disappear, move or remain?

“Move” means a maintained adapter supplies translation; our compatibility tests still verify the required result.

| M6 responsibility | Through ACP | What the application must still establish |
|---|---|---|
| Python Codex SDK/generated types and app-server framing | **Disappear from our transport implementation** if fully replaced; move behind ACP adapter | ACP types stay outside domain; pin/test the ACP adapter and its dependencies |
| `serverInfo`/`userAgent` parsing, thread/turn request shapes, notification routing | **Mostly move** into adapter | Provenance of the executable chain, early-event handling, exact internal attempt/session correlation and no duplicate launch |
| SDK `env` merge and close implementation workarounds | **Specific code paths may disappear** | Sanitized launch, trusted configuration, bounded shutdown and settlement remain; adapter adds another process |
| Complete provider-feature inventory matching | **Never a standard ACP requirement; should be narrowed with either transport** | Authority-bearing configuration and all reachable effects must still be covered by a reviewed profile |
| Effective sandbox, shell/network/web policy, hooks/plugins/MCP/delegation | **Remain; standard ACP does not supply a complete effective-policy attestation** | Verify actual enforcement before inference; client fs capabilities do not constrain harness-local tools |
| Deny-all approval ceiling | **Remains, with a different translation** | Stock Codex ACP read-only/on-request differs; auto-denying callbacks cannot prove universal mediation |
| Model/provider/effort and auth | **Discovery/config transport can become common** | Concrete approved binding, no silent fallback, usable harness auth, scoped credential exposure and no secret persistence |
| Runtime/version compatibility | Python SDK pin may vanish; **profile becomes adapter + ACP protocol/SDK + Codex binary** | Exact tested versions and executable identity; reported agent version alone is insufficient |
| Owner generation, descendant scope, budgets, cancellation and restart | **Remain** | Cancellation receipt semantics per protocol/profile, independent settlement, missing receipt → unknown; history is not reattachment |
| Steering/effective input revision | **Remains unsatisfied for M6** | Keep unsupported until proven; an extension that starts a turn cannot silently satisfy in-turn steering |
| Artifacts, schema/content/hash and workspace identity | **Remain service-owned** | ACP text/diffs are observations, not complete validated deliverables |
| Ledger transactions, immutable snapshots, reservations, retries | **Unchanged** | Persist intent before effect; external ACK separately; never resubmit an ambiguous attempt |

**Adoption gate:** a source/fixture prototype must demonstrate the exact no-escalation policy, all-surface authority coverage before launch, fresh-session identity, unknown-launch behavior, cancellation and bounded settlement, effective model binding and one validated output contract. Do not substitute optional adapter extensions or draft v2 semantics silently. The stock adapter fails several of these unchanged assumptions; adopt ACP for reduced transport duplication only after resolving them. No immediate ACP migration is necessary to correct the brittle configuration gate.

## Evidence register and limits

Sources were inspected on 2026-10-02. Codex source is the project's exact 0.159.2 pin; current docs are corroboration, not proof of matching every pinned option. Claude Python SDK source is `bfb895c6ef46e095191938b4eda798a025957c09` (0.2.163); the separate Claude Code binary still needs its own deployment pin. OpenCode source is `1ddb0873aee50d209d1a8d7f91b89c5daf692d49` (1.18.34); entrypoint-specific examples are not guarantees for every runtime mode. AWS/Ollama/vLLM and ACP documentation is versioned or date-stamped where available, but otherwise rolling. No universal host enforcement or remote settlement was experimentally certified.

- **O1:** [Codex security and network coverage](https://learn.chatgpt.com/docs/agent-approvals-security).
- **O2:** [Codex configuration: telemetry, history and related settings](https://learn.chatgpt.com/docs/config-file/config-reference); [managed configuration distinguishes feature flags from security sensitivity](https://learn.chatgpt.com/docs/enterprise/managed-configuration).
- **O3:** [Pinned feature registry and consumer descriptions](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/features/src/lib.rs); [pinned config schema](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/core/config.schema.json).
- **O4:** [Pinned SDK environment, initialization and close](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py).
- **O5:** [Pinned history status handling](https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_lifecycle.rs).
- **C1:** [Claude sandbox scope](https://code.claude.com/docs/en/sandboxing#what-runs-outside-the-sandbox).
- **C2:** [Claude SDK permissions](https://code.claude.com/docs/en/agent-sdk/permissions).
- **C3:** [Claude secure deployment](https://code.claude.com/docs/en/agent-sdk/secure-deployment); [configuration sources](https://code.claude.com/docs/en/agent-sdk/configuration).
- **C4:** [Claude interruption](https://code.claude.com/docs/en/agent-sdk/python#example---using-interrupt); [pinned SDK process cleanup](https://github.com/anthropics/claude-agent-sdk-python/blob/bfb895c6ef46e095191938b4eda798a025957c09/src/claude_agent_sdk/_internal/transport/subprocess_cli.py#L962).
- **C5:** [Claude telemetry and executable header helper](https://code.claude.com/docs/en/monitoring-usage).
- **B1:** [Bedrock client-side tool execution](https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html).
- **B2:** [Bedrock Converse API/IAM/configuration](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html).
- **B3:** [Converse streaming events](https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html); [stored Responses cancellation is a different API profile](https://docs.aws.amazon.com/bedrock/latest/userguide/inference-prereq.html).
- **L1:** [Ollama tool calling](https://docs.ollama.com/capabilities/tool-calling).
- **L2:** [Ollama local/cloud authentication](https://docs.ollama.com/api/authentication).
- **L3:** [Ollama server, storage and cloud configuration](https://docs.ollama.com/faq).
- **L4:** [Ollama chat response semantics](https://docs.ollama.com/api/chat).
- **V1:** [vLLM engine authority-bearing startup arguments](https://docs.vllm.ai/en/stable/configuration/engine_args/).
- **V2:** [vLLM security: plugins, network, API-key and media limits](https://docs.vllm.ai/en/latest/usage/security/).
- **V3:** [vLLM tool-call output](https://docs.vllm.ai/en/stable/features/tool_calling/).
- **A1:** [ACP v1 initialization/capabilities](https://agentclientprotocol.com/protocol/v1/initialization).
- **A2:** [ACP v1 filesystem](https://agentclientprotocol.com/protocol/v1/file-system); [terminal lifecycle](https://agentclientprotocol.com/protocol/v1/terminals).
- **A3:** [ACP permission requests](https://agentclientprotocol.com/protocol/v1/tool-calls#requesting-permission); [session/MCP setup](https://agentclientprotocol.com/protocol/v1/session-setup).
- **A4:** [ACP v1 prompt/cancellation](https://agentclientprotocol.com/protocol/v1/prompt-turn#cancellation); [generic request cancellation](https://agentclientprotocol.com/protocol/v1/cancellation).
- **A5:** [Draft ACP v2 migration, ownership and receipt changes](https://agentclientprotocol.com/protocol/v2/migration).
- **A6:** [ACP v1 extensibility](https://agentclientprotocol.com/protocol/v1/extensibility); [draft v2 unknown variant handling](https://agentclientprotocol.com/protocol/v2/extensibility).
- **P1:** [OpenCode pinned security boundary](https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/SECURITY.md#no-sandbox).
- **P2:** [OpenCode plugin shell access, environment and replacement tools](https://opencode.ai/docs/plugins/); [permission behavior](https://opencode.ai/docs/permissions/).
- **P3:** [OpenCode configuration precedence](https://opencode.ai/docs/config/#precedence-order); [MCP server/auth configuration](https://opencode.ai/docs/mcp-servers/).
- **P4:** [Pinned SDK server](https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/sdk/js/src/server.ts); [stop implementation](https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/sdk/js/src/process.ts).
- **P5:** [Pinned compaction plugin path](https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/session/compaction.ts#L372); [cached approvals](https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/permission/index.ts#L141).
- **X1:** [Codex ACP pinned dependency manifest](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/package.json).
- **X2:** [Codex ACP app-server transport](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexJsonRpcConnection.ts#L15).
- **X3:** [Codex ACP initialize options](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpClient.ts#L161).
- **X4:** [Codex ACP approval/sandbox mode mapping](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/AgentMode.ts#L40).
- **X5:** [Codex ACP effective configuration/MCP construction](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpClient.ts#L850).
- **X6:** [Codex ACP advertised support](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpServer.ts#L362).
- **X7:** [Codex ACP steering extension](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/AcpExtensions.ts#L120); [new-turn fallback](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpServer.ts#L1603).
- **X8:** [Codex ACP exit/termination handling](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/index.ts#L106).
- **X9:** [Codex ACP extension evidence limits](https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/docs/air-extensions.md#L723).

Validation performed for this review: read-only classifier reproduction, source/citation inspection, report link/structure checks and preservation checks for existing tracked files. A documentation review cannot certify cross-runtime conformance. The eight architecture decisions were subsequently approved and promoted as linked above. Corrective implementation remains pending; any ACP adoption requires its separately scoped conformance gate.

[O1]: https://learn.chatgpt.com/docs/agent-approvals-security
[O2]: https://learn.chatgpt.com/docs/config-file/config-reference
[O3]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/features/src/lib.rs
[O4]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/sdk/python/src/openai_codex/client.py
[O5]: https://github.com/openai/codex/blob/ff6aec96948b70d94983af2641a6b67c94faeff5/codex-rs/app-server/src/request_processors/thread_lifecycle.rs
[C1]: https://code.claude.com/docs/en/sandboxing#what-runs-outside-the-sandbox
[C2]: https://code.claude.com/docs/en/agent-sdk/permissions
[C3]: https://code.claude.com/docs/en/agent-sdk/secure-deployment
[C4]: https://code.claude.com/docs/en/agent-sdk/python#example---using-interrupt
[C5]: https://code.claude.com/docs/en/monitoring-usage
[B1]: https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use-client-side.html
[B2]: https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
[B3]: https://docs.aws.amazon.com/bedrock/latest/userguide/conversation-inference.html
[L1]: https://docs.ollama.com/capabilities/tool-calling
[L2]: https://docs.ollama.com/api/authentication
[L3]: https://docs.ollama.com/faq
[L4]: https://docs.ollama.com/api/chat
[V1]: https://docs.vllm.ai/en/stable/configuration/engine_args/
[V2]: https://docs.vllm.ai/en/latest/usage/security/
[V3]: https://docs.vllm.ai/en/stable/features/tool_calling/
[A1]: https://agentclientprotocol.com/protocol/v1/initialization
[A2]: https://agentclientprotocol.com/protocol/v1/file-system
[A3]: https://agentclientprotocol.com/protocol/v1/tool-calls#requesting-permission
[A4]: https://agentclientprotocol.com/protocol/v1/prompt-turn#cancellation
[A5]: https://agentclientprotocol.com/protocol/v2/migration
[A6]: https://agentclientprotocol.com/protocol/v1/extensibility
[P1]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/SECURITY.md#no-sandbox
[P2]: https://opencode.ai/docs/plugins/
[P3]: https://opencode.ai/docs/config/#precedence-order
[P4]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/sdk/js/src/server.ts
[P5]: https://github.com/anomalyco/opencode/blob/1ddb0873aee50d209d1a8d7f91b89c5daf692d49/packages/opencode/src/session/compaction.ts#L372
[X1]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/package.json
[X2]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexJsonRpcConnection.ts#L15
[X3]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpClient.ts#L161
[X4]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/AgentMode.ts#L40
[X5]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpClient.ts#L850
[X6]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/CodexAcpServer.ts#L362
[X7]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/AcpExtensions.ts#L120
[X8]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/src/index.ts#L106
[X9]: https://github.com/agentclientprotocol/codex-acp/blob/68d7d2d5ddfc0ed5746f9f6130892dda685e65dd/docs/air-extensions.md#L723
