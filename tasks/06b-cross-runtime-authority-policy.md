# Milestone 6 follow-up — cross-runtime authority policy

## Objective and authority

Implement the smallest correction to the current Codex admission policy supported by the approved [cross-runtime review](../docs/research/CROSS_RUNTIME_AUTHORITY_REVIEW.md) and [canonical WorkerBackend contract](../docs/IMPLEMENTATION_PLAN.md#4-workerbackend-contract). Approval date: 2026-10-02; reviewed implementation baseline: `c55c20a8d43734e49ee6762b58d74dc5f60c5c14`. Verify current checkout/source before changing it; preserve unrelated work.

M6 remains incomplete: the audit records a read-only live smoke pass, but corrected admission is not implemented and exact-turn interruption is unverified. This is a corrective M6 implementation task, not Task 07. Preserve [original Task 06](06-codex-harness-backend.md) as the historical initial scope. The canonical authority/drift rules supersede only its exhaustive configuration-equality assumptions; all other M6 guarantees remain in force. Stop before M7.

Deliver operational reviewed-setting semantics, an adapter-local authority/required-guarantee projection, separate admission and forensic hashes, and evidence-backed acceptance of reviewed harmless drift. Keep the public Codex SDK transport and exact 0.159.2 SDK/CLI pin. Do not use an upgrade, broad whitelist or alternate backend to make policy checks pass.

## Read first

- [AGENTS.md](../AGENTS.md), [canonical plan](../docs/IMPLEMENTATION_PLAN.md), [integration audit](../docs/INTEGRATION_AUDIT.md), [development policy](../docs/DEVELOPMENT.md).
- [Task 05](05-bounded-semantic-decision-infrastructure.md), original Task 06 and the supporting cross-runtime review. Follow canonical contracts; the research intake backlog is outside this task and must not be accessed.
- Current `src/orchestrator/backends/codex_backend.py`, its owner helpers, `src/orchestrator/domain/backend.py`, coordinator preflight/persistence/control/recovery boundaries and relevant fixture/tests. Read affected contracts before editing; preserve M5 worker/inference identity separation.

## Current behavior to correct

`_ReviewedRuntimeSetting` retains a `classification` that `_configuration_issues` does not consult. Its categories mix semantic risk with presence requirements. The gate checks effective config and layers against reviewed values/types and rejects unknown keys; `start()` independently compares the entire sanitized configuration/layer hash. Relaxing one parser rule cannot fix this second equality gate.

The feature-list fixture is an inventory, not an implemented general feature-registry classifier or permission receipt. Existing `PreflightFact` and `BackendPreflightSnapshot` structures can carry the bounded projection through versioned facts/evidence. The coordinator already persists accepted preparation and owner identity before submission. Keep provider interpretation inside the adapter and avoid spreading provider flags into the coordinator.

## Admission rule and evidence

Admission is closed-world for authority-bearing behavior and required correctness guarantees. Tolerate unknown behavior only when either:

1. A pinned consumer contract demonstrates bounded observational/no-op handling without affecting authority or required semantics; or
2. An independently enforced boundary fully contains every reachable effect within the accepted ceiling and preserves all required guarantees.

Neither an unfamiliar name, `false` value, SDK extra-field acceptance, successful smoke test nor provider capability claim establishes harmlessness. Complete containment must cover helpers/hooks/plugins, auth material, IPC/control endpoints and remote effects as applicable; a shell-only sandbox is insufficient. Reject unclassified executable/effectful paths before their effects can begin, including startup side effects before app-server/model launch where required. Rechecking only after a hook initialized cannot establish prelaunch safety.

Keep present, enabled, available, permitted, enforced, observed and authority-widening separate. Record unavailable/unverified evidence honestly; a non-null value is not enforcement proof. Preserve strict authored domain/config schemas and closed essential lifecycle discriminators. Tolerance in a reviewed informational event path does not authorize unknown executable configuration or control requests.

## 1. Operational reviewed-setting semantics

Refactor the existing policy rather than deleting classification or broadly accepting extra provider fields. Represent and apply these independently:

| Element | Required behavior |
|---|---|
| Effect/semantic classification | Authority/effect-bearing (A), behavior within established authority (B), observational only (C), with pinned consumer evidence |
| Presence policy | Required, optional or forbidden independently of effect class |
| Value/type validation | Explicit expected values, allowed values/ranges and type rules; missing and null must not become interchangeable without evidence |
| Evidence requirements | Required pinned source/fixture or containment evidence, scope/coverage and explicit rejection reasons |
| Guarantee dependencies | Authority, lifecycle/control, identity, output, budget, provenance or other mandatory semantics, regardless of A/B/C label |

Classification must influence the projection/evidence/validation decision, not remain an unused label. No rule equivalent to `if inert_metadata: allow anything`. Re-review `network_proxy`, `windows_sandbox_service`, `history`, `project_root_markers` and instruction inclusion: they can affect containment, retention/recovery, configuration discovery or required provenance. Telemetry exporters/helpers, compaction hooks and cached approvals are not automatically harmless metadata/behavior. Document the reviewed consumer and dependencies for each newly tolerated value; keep all unreviewed paths closed.

## 2. Versioned authority/guarantee projection

Implement an adapter-local, deterministic projection with an explicit revision and policy-profile identity. Cover the dimensions relevant to M6:

- Filesystem/data: read/write/retention scope, workspace and runtime-state identity; read-only does not mean project-only reads.
- Process/executable: pinned executable and relevant helper/tool identities, allowed execution and descendant ownership.
- Network/remote services: distinguish shell egress, model/auth traffic, web, integrations, telemetry and control ingress.
- External tools/delegation: approved implementation/server identities, disabled unintended MCP/apps/plugins/hooks/delegation and enforceable ceilings.
- Principal/auth material: which executor can access/use which approved principal or secret reference/scope, with exposure limitations.
- Durable/autonomous effects: reachable persistent/background/remote effects and their owner/settlement limits, without implementing a nested-operation ledger.
- Required lifecycle/control, model/effort, artifact/output, budget/provenance and executable/configuration-source identity guarantees.

Associate relevant facts with scope, executor, permission enforcer, lifecycle owner, required guarantee, evidence/provenance and known gaps. Available capabilities exceeding the requested scope are acceptable only when verified enforcement makes that excess unreachable. Unknown mandatory coverage fails closed.

Use existing preflight fact groups, evidence references and immutable snapshots. Sanitize before persistence or hashing; never store/hash raw credentials, tokens, cookies or account responses as provenance. Use non-secret scoped principal identity/evidence and preserve existing secret validators. Do not claim evidence not exposed by a verified boundary.

Define stable serialization and a projection digest that includes required policy/evidence identity but excludes incidental timestamps and reviewed noncritical observations. Distinguish compatibility/profile revision from physical storage schema version. Preserve historical receipt interpretation; do not backfill invented guarantees or mutate old records. Require the corrected projection for new corrected-profile attempts; missing required evidence cannot silently fall back to permissive launch. Historical inspection remains conservative and cannot turn old evidence into new launch permission.

No generic persistence/schema migration is authorized for conceptual cleanliness. If existing storage demonstrably cannot represent required typed persisted scope or evidence, stop and report the concrete deficiency and minimal proposed change before widening scope. No universal capability/tool ontology.

## 3. Narrow inventory admission

Retain pinned inventory fixtures for upstream drift detection, authority-path discovery, compatibility review and forensic evidence. Bind admission to the bounded authority/required-guarantee projection and executable/configuration-source identity, not exhaustive equality of every feature name/value at every launch.

Prove a reviewed no-op/display setting harmless through its actual pinned consumer or complete enforcement coverage. A removed flag may coexist with always-on behavior; a deprecated/false flag is not proof that a tool is absent. Inventory differences revealing new or unclassified executable/authority paths still block. Preserve enough sanitized evidence to explain both rejection and tolerated drift.

## 4. Split admission-critical and forensic drift

Preserve the full sanitized effective configuration/layer hash for diagnostics and change detection. Store or derive a separate stable admission projection/hash using the existing fact/receipt structure. Keep exact identity checks for the SDK/runtime executable chain, profile, configuration sources and principals, plus every required guarantee.

During preflight and immediately before `turn/start`, validate current effective policy and compare its critical projection/evidence with the committed accepted record. Reject unexpected authority drift, executable/profile/principal changes, unknown configuration sources, unclassified effectful paths and lost required guarantees. Changing a tool implementation under the same name must reject whenever that implementation identity establishes trust. Required lifecycle/output/budget/provenance changes remain critical even when labeled B or C.

Accept reviewed noncritical display/config changes when the authority/guarantee projection remains valid and stable. Record an attributable sanitized diagnostic/event with accepted and observed forensic fingerprints and classification/evidence references, using existing event/diagnostic facilities. Do not rewrite the immutable preflight receipt, original resolved spec or accepted projection. Repeated preflight/inspection must never broaden an accepted grant. Critical drift requires rejection and the existing explicit attempt/preparation rules, never silent renegotiation or duplicate submission.

## 5. Preserve hard M6 guarantees

Keep exact runtime/SDK/executable pins, immutable preflight/owner receipts, permission ceilings, deny-all/no-escalation, verified sandbox/network/integration/delegation restrictions, concrete model/effort/output contracts and artifact validation. Preserve one fresh client/thread per attempt and single submission, atomic admission/event/reservation/dispatch intent, separately committed external acknowledgement and provider-neutral coordinator authority.

Preserve independent bounded process settlement, exact owner generation/identity, `outcome_unknown`, reservation retention, conservative restart/reconciliation and classified/budgeted retry as a new attempt. Provider terminal events, history and SDK close remain insufficient settlement evidence. Keep steering unsupported and exact-turn interrupt semantics unchanged. A more tolerant configuration policy must not weaken authority or falsely certify lifecycle guarantees.

## Deterministic offline regression requirements

Extend existing Codex backend/lifecycle/owner tests and fixtures at the smallest boundary; retain M1–5 regression coverage. Pair acceptance cases with adversarial rejection cases so a blanket bypass cannot pass. Ordinary CI remains credential-free and offline. Require at least:

| Fixture/change | Expected evidence/result |
|---|---|
| Reviewed benign display/config drift | Accepted with pinned harmlessness evidence and bounded diagnostic |
| Changed full sanitized forensic hash, unchanged critical projection | Submission allowed; original receipt/spec hashes unchanged; drift recorded |
| Authority projection drift | Rejected before turn; no replacement snapshot or wider grant |
| Unknown authority-bearing feature, including disabled-looking unknown | Rejected without consumer/containment proof |
| Extra reviewed informational metadata or unknown observational event | Tolerated only in the appropriate bounded/sanitized event/consumer path; never an executable-config or essential-status exemption |
| Unknown executable setting or configuration source/layer | Rejected before relevant effect; no initialization of unknown code |
| Same logical tool name, changed implementation identity | Rejected when identity establishes trust |
| Ineffective or changed sandbox/egress enforcement | Rejected despite configured restriction/claimed capability |
| Inherited plugin/hook/delegation surface | Blocked before initialization where required; no authority from overridden/hidden layers |
| Principal/auth exposure or executable/profile identity mismatch | Rejected; no credential persistence or permissive fallback |
| Required lifecycle/control guarantee mismatch | Rejected even if the changed field is labeled B/C |
| Required output, budget or provenance guarantee mismatch | Rejected independently of authority scope and category |
| Repeated preflight/inspection | No authority expansion, receipt mutation, replay or fabricated verified facts |
| Projection revision/serialization and historical receipts | Stable deterministic digest; historical reads preserved; new attempts require corrected evidence |
| Missing/invalid evidence, wrong presence/type/value | Classification alone cannot authorize; fail with precise reason |
| M6 owner/process and unknown-outcome regressions | Child survival, owner reuse, parent loss, lost launch/control replies, EOF and unsettled terminal retain existing settlement/reservation behavior |
| M1–5 regressions | Decisions, topology, immutable specs, persistence, retries, controls and recovery unchanged |

Version fixtures with exact runtime/source/policy identity; identify synthetic data versus captured live evidence. Existing subprocess fixtures may use local controlled processes, never a live provider by default. Preserve alternate ownership fixtures without building a second backend.

## Gated live validation after implementation

This corrective task requests the bounded post-implementation live checks below. Run them only after all required offline checks pass, with explicit live-test opt-in, the approved dedicated `ORCHESTRATOR_CODEX_HOME`, concrete permitted `ORCHESTRATOR_CODEX_LIVE_MODEL` and `ORCHESTRATOR_CODEX_LIVE=1`. Never default to the normal user home, copy credentials, change login state or start an open-ended paid retry loop. If authentication/configuration or required safety evidence is missing, report blocked rather than bypassing it.

1. Rerun `tests/test_codex_backend_live.py::test_codex_live_one_short_read_only_turn` alone, using the existing bounded read-only fixture and timeout/cleanup controls. Record whether it passed preflight, created a fresh thread, acknowledged/executed a real turn, validated the output and independently settled its owner. A preflight-only success is not a smoke pass.
2. Only after that smoke passes the required boundary, run `tests/test_codex_backend_live.py::test_codex_live_exact_turn_interrupt_and_cleanup`. Verify exact attempt/thread/turn targeting, accepted control evidence and independent bounded settlement. A rejected/lost acknowledgement, saved interrupted history alone or natural completion before interruption is failed/uncertain/inconclusive control coverage, never a pass.
3. Keep unsupported controls unsupported; do not weaken interruption semantics to satisfy a test. Preserve unknown outcomes/reservations and retain sanitized evidence on failure. If the real runtime exposes a new authority-bearing surface outside the reviewed projection, fail closed, report it and stop rather than silently expanding policy.

Report live outcomes separately from offline correctness, including reached boundary, sanitized runtime/profile/model identity, exact receipts/evidence references and remaining limitations. The historical smoke pass does not certify the corrected implementation. Leave M6 incomplete if the approved live boundary or a hard guarantee remains unverified. No live model/runtime calls are part of the architecture-promotion run that generated this task.

## Non-goals

No ACP implementation/dependency or Codex ACP migration; no second real backend or Claude/OpenCode/Bedrock/Ollama/vLLM adapter. ACP remains the preferred optional future interoperability protocol only for conformant profiles under the canonical adoption gate. Optional documentation/test seams do not authorize transport work.

No universal capability ontology, broad package restructuring, native model runtime, model-routing changes, UI or website work. No M7 ContextAssembler, Git worktrees or deliverable writes. CAND-005 remains unresolved: no durable nested tool-operation model, app-owned nested asynchronous/effectful execution or new operation ledger. No generic migration absent a separately reviewed concrete deficiency.

## Validation, acceptance and delivery

After implementation, run the repository's required offline checks:

```sh
uv run pytest -m 'not live'
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv lock --check
uv run agent-orchestrator validate-config presets/agents.toml
uv run agent-orchestrator validate-config presets/workflows/feature.toml
uv run agent-orchestrator validate-config config/project.example.toml
uv run python scripts/export_schemas.py
```

Use existing loader/schema tests to validate the remaining product/development configuration and inspect schema output; no generic schema change is expected. Do not weaken failing tests. Then perform only the gated live sequence above.

Acceptance requires operational classification with independent presence/value/evidence/dependency checks, a versioned authority/guarantee projection, stable critical and forensic hash separation, diagnostic benign drift and every listed rejection/settlement regression. No source of unknown authority may be ignored merely to make activation succeed. Update the plan/audit and relevant fixtures to distinguish implemented behavior, offline verification, live results and remaining limitations; do not claim M6 complete without its full approved boundary.

Inspect the final diff/status, preserve unrelated files and the original Task 06, and commit only intended validated implementation changes per AGENTS.md. Push only when authorized. If a required check fails, report it and preserve the work without presenting acceptance as complete. Stop before M7.
