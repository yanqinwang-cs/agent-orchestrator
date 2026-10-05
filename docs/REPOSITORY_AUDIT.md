# Agent Lab repository audit

Audited **2026-10-05** in the current checkout on branch `codex/research`, against baseline `e0465e3161406eb037c324333dff00cfeff7a07b` and the working-tree [AGENTS.md](../AGENTS.md). This is an audit and documentation/control cleanup. It does not authorize or implement the proposed code migration in [CODEBASE_MIGRATION_PLAN.md](CODEBASE_MIGRATION_PLAN.md).

## Scope and evidence

The inventory covers **all 143 files tracked at task start**, including hidden configuration, all 30 production Python files, three scripts, 56 generated schemas, 12 test/conftest modules, 14 fixtures, build/dependency metadata, presets, and project-control material. Source inspection included module dependencies, class fields, function/method inventories, lifecycle/control flow, persistence SQL/migrations, resolver/validation logic, tests/assertions and dynamic fixture use. Each generated schema was parsed and its properties/definitions examined; registry consistency is validated by the existing test.

Pre-existing changes were the Agent Lab rewrite of `AGENTS.md`, modified `.codex/config.toml`, and untracked local skills/rules, skill lock, five old tasks, three agent-workflow documents, and a research backlog. The two tracked user-modified files and unrelated local tooling are preserved. Nine clearly obsolete untracked project controls were assessed and removed under the cleanup prompt; because Git had no copies, their exact bytes were preserved outside the repository at `/private/tmp/agent-lab-cleanup-audit/untracked-controls/`. That temporary recovery location is local and may be purged; it is not a new active archive or project authority.

`KEEP` means consistent/useful now, including documents rewritten in this task. `ADAPT-LATER` means unchanged code or durable infrastructure retained for this task's behavior-preservation boundary; it includes candidates for later deletion, not a commitment that they must survive. `DELETE-NOW` is clear obsolete non-code cleanup. `REVIEW` marks a real unresolved ownership/use decision. The tracked totals are **6 KEEP, 127 ADAPT-LATER, 9 DELETE-NOW, 1 REVIEW**. Nine additional untracked controls were deleted, for **18 removed files overall**.

## Context pollution and cleanup

The old README claimed a personal specialist-workflow product, mandated a coordinator/ledger, and linked an “authoritative” ten-milestone implementation plan. It also said only fake execution existed despite the implemented Codex adapter. The old integration/research documents promoted old admission/ACP decisions and stop-control candidates. Completed task specifications and the untracked task queue directed future agents into old milestones. The candidate backlog pointed accepted changes back to the deleted plan. The issue/triage/domain guides imposed a separate issue-map workflow and hypothetical `CONTEXT.md`/ADR continuity structure without an active Agent Lab role.

These controls were deleted rather than retained as governing history. README and development guidance now distinguish current intent, existing behavior, legacy fixtures, and unimplemented migration. The unused `.env.example` was removed: neither the CLI nor config loader loads `.env`, and most host/UI settings had no consumer. The actually used Codex environment variables are documented in surviving development guidance.

There was no tracked repository `MEMORY.md`, `CONTEXT.md`, `CONTEXT-MAP.md`, additional project instruction file, CI workflow, or license file. No historical archive directory was introduced. `AGENTS.md` was not edited by this task; the new audit is descriptive and the migration plan is explicitly a review proposal. Installed third-party skill documentation, including its nested `AGENTS.md`, is tooling documentation rather than project-level continuity authority.

### Additional untracked controls removed

| Path | Classification | Reason |
| --- | --- | --- |
| `docs/agents/domain.md` | DELETE-NOW | Imposes another context/glossary/ADR workflow; no active accepted Agent Lab role. |
| `docs/agents/issue-tracker.md` | DELETE-NOW | Old issue-map/claim/publish instructions are not needed for the authorized cleanup or new research scope. No GitHub issue was changed. |
| `docs/agents/triage-labels.md` | DELETE-NOW | Companion triage control has no surviving workflow consumer. |
| `docs/research/CANDIDATE_CHANGES.md` | DELETE-NOW | Old architecture promotion backlog and research-monitor instructions point to a superseded authority. |
| `tasks/02-durable-run-ledger.md` | DELETE-NOW | Old ledger milestone task. |
| `tasks/03-bounded-fake-execution.md` | DELETE-NOW | Old scheduler/workflow milestone task. |
| `tasks/04-controls-and-recovery.md` | DELETE-NOW | Old intervention/recovery milestone task. |
| `tasks/05-bounded-semantic-decision-infrastructure.md` | DELETE-NOW | Completed old bounded-router milestone task. |
| `tasks/06-codex-harness-backend.md` | DELETE-NOW | Unfinished Codex roadmap is not the new project's required next task. |

### Local items preserved for review

| Item | Assessment |
| --- | --- |
| `.agents/skills/` and `skills-lock.json` | Untracked, separately installed generic tooling; preserve rather than silently remove the user's installations. Browser/discovery/frontend skills may support later work; video-edit has no established repository role. Review which installs should remain project-local or be ignored; none is a required runtime dependency. |
| `.codex/rules/default.rules` | Untracked local `git push` allow rule, with old milestone wording. Preserve unrelated permission configuration; review ownership/scope and stale justification. It permits an execution request but supplies no user authorization. `AGENTS.md` still governs push delivery; no push occurred. |
| `.no-mistakes.yaml` | Tracked optional external review-tool selector. No in-repository consumer or current workflow owner was established; preserve until its intended use is clarified. |
| Ignored caches and local runtime data | Outside the tracked inventory. No user databases, authentication state, or installed tools were purged or converted. Build/test outputs used temporary locations or standard ignored caches. |

## Code subsystem assessment

The checkout contains useful tested mechanics, but **no experiment definition, dataset/task-set contract, benchmark evaluator, representation strategy interface, or public result surface**. Keeping the whole runtime would make those new capabilities pay for an unrelated coding-workflow product.

| Subsystem and inspected evidence | Reusable behavior | Obstruction and proposed disposition |
| --- | --- | --- |
| [Domain/configuration](../src/orchestrator/domain/models.py), [loader](../src/orchestrator/config.py), [validation](../src/orchestrator/validation.py) | Strict unknown-field rejection, bounded permissions/budgets and cross-reference diagnostics. | Closed coding roles, repair conditions, fixed stage/completion categories, profile-to-backend coupling and worktree policy. Loader requires exactly six workflows and every shipped config. Replace contracts; extract narrowly useful checks. |
| [Resolution](../src/orchestrator/resolution.py) | Pure resolution, frozen snapshots, canonical JSON SHA-256, explicit binding failures and permission narrowing. | RunSpec freezes specialist profiles and workflow slots; canonical JSON describes configuration identity, not an optimal universal message representation. Reuse identity mechanics and redesign only the reviewed experiment definition. |
| [Artifacts](../src/orchestrator/artifacts/store.py) | Streamed content hashes, atomic rename, safe managed paths, manifest-before-read validation, corruption and failed-publication handling. | Publication requires an existing attempt and a legacy revision mutation. Extract store mechanics behind experiment/run ownership; do not preserve all ledger tables to reuse filesystem integrity. A crash can leave unreferenced bytes; this is not distributed atomic storage. |
| [Ledger](../src/orchestrator/persistence/ledger.py), [models](../src/orchestrator/persistence/models.py), [migrations](../src/orchestrator/persistence/migrations.py) | SQLite foreign keys, WAL/full synchronous file-backed commits, revision checks, command idempotency, immutable snapshots/results, append-only events and reopen tests. | Giant LedgerMutation and foreign-key graph encode projects→runs→stages→attempts plus control/decision/outbox/reservation tables. Database is v5, distinct from JSON model schema-v1 labels. Do not reuse old rows as experiment records or mutate them in this task. |
| [Coordinator](../src/orchestrator/execution/coordinator.py) | Controlled unknown-outcome handling, failure classification, bounded retry and separate launch acknowledgement. | 4,058 lines implement stage/slot ordering, Feature repair, verification topology, capacity reservations, dispatch, controls and restart reconciliation. Integration stages compute a synthetic revision hash; they do not integrate real Git changes. Replace execution with external harness/runtime rather than extend this scheduler. |
| [Decision contracts](../src/orchestrator/domain/decisions.py), deterministic/fake decision adapters | Explicit evidence and inference identity, stale-evidence/run rejection, score semantics/calibration, abstention, bounded outcomes, controlled async replies. | Only deterministic first-allowed and scripted engines exist; configured action is stage `redirect_select_one`. Fixture normalization across four inference shapes is not measured evidence of native/readout model performance. Optional for decision experiments, not the core evaluator or universal communication contract. |
| [Worker seam](../src/orchestrator/backends/protocol.py), [fake worker](../src/orchestrator/backends/fake.py) | SDK-independent adapter boundary, manual clock and event/control barriers. | Protocol consumes AgentRunSpec and requires steer/interrupt/inspect/close plus worker handles. Coordinator defaults to FakeClock; no wall-time progression should be assumed without driving it. Adapt a smaller invocation seam and test controls as needed. |
| [Codex adapter](../src/orchestrator/backends/codex_backend.py), [report retention](../src/orchestrator/backends/codex_output.py) | Pinned/version-checked preflight, authority/provenance projections, exact request identity, bounded report byte retention and local hashes. | 4,012-line SDK/host-specific implementation. Only read-only `report` output is admitted; network/web/integrations/nested agents/skills and broader tool requests are rejected. Core BackendSettings also embeds Codex-specific configuration. Optional comparison adapter, pending human choice. |
| [Process owner](../src/orchestrator/backends/codex_owner.py), [bridge](../src/orchestrator/backends/codex_bridge.py), [coordinator ownership](../src/orchestrator/persistence/ownership.py) | Separate child reaping, process-group emptiness, bridge disconnect, and OS lock generations. | Local process/Unix socket/fcntl assumptions do not generalize to hosted sessions. Receipts do not prove settlement of detached managed descendants or remote effects. Keep only with a concrete retained local backend need. |
| [CLI](../src/orchestrator/cli.py), scripts and schemas | Runnable validation CLI, schema exporter/byte-check and supplemental TOML checker. | Existing package/CLI naming and Milestone 3 message remain in code by this task's hard stop. No execution CLI/UI. The starter check and registry encode old topology/contracts. Migrate entry points with consumers; no behavior was edited here. |

### Specific legacy concepts

- **Workers and specialist profiles:** possible harness-local implementation detail, not mandatory generic experiment entities. The current eleven-role catalog has no independent experimental justification.
- **Factories:** no domain Factory or worker-factory persistence abstraction was found. `script_factory`, `client_factory`, and `owner_factory` are ordinary dependency-injection callbacks; `default_factory` and SQLite `row_factory` are unrelated implementation constructs. Keep only with the adapter/test code that uses them.
- **Attempts:** repeated execution and submission provenance can be useful, but stage/slot lineage, retry authorization and receipt fields are old product semantics. Distinguish a planned experimental repetition from a backend retry/submission without importing the whole current contract.
- **Reservations and dispatch/outbox:** active scheduler capacity and durable-launch machinery, not dead code today. Prefer external scheduling; retain only the smallest evidence/idempotency mechanism justified by a remote-submission failure case. Do not introduce a custom distributed scheduler.
- **Interventions and reconciliation:** ACK, observed terminal outcome, and effect settlement are distinct facts worth preserving. Pause/resume/steer/redirect/retry as a universal product control model is not justified; capabilities belong to adapters. Uncertainty should remain inspectable rather than be converted to success.
- **Legacy presets/persistence:** both remain active consumers of old contracts. Their eventual deletion must include loader, schema registry, model imports, tests and metadata in one validated retirement sequence.

## Dependency, test, configuration and schema findings

The direct runtime dependencies are `pydantic>=2.10,<3` and exactly `openai-codex==0.159.2`. The lock also brings the pinned `openai-codex-cli-bin`; this executable dependency is needed only by the old Codex adapter. `packaging` is shared with test tooling, so do not indiscriminately delete it. Pydantic and Python's SQLite/path/hash/async primitives can support experiments without provider-specific domain types. Dev dependencies (pytest/pytest-asyncio, Ruff, mypy and their transitive helpers) remain useful. There is no Deep Agents, LangChain/LangGraph, AWS SDK or AgentCore dependency today; none was introduced.

All test modules and fixtures protect implemented behavior; none was proven dead by this audit. Decision fixtures are selected dynamically using stems, so a literal filename search alone would falsely classify them as unused. The schema export test compares all 56 schemas against current models. Offline tests for all six workflows and control/repair/reservation behavior are useful regressions until those behaviors are deliberately removed, not evidence that Agent Lab needs them. Artifact corruption/traversal/failed writes, canonical immutability, stale evidence, transaction rollback/idempotency and bounded adapter failure properties are the main candidates to carry forward. Two live provider tests stay opt-in.

The six workflow presets, agent catalog and three application/development TOMLs are **required migration dependencies**, not abandoned files safe to delete now. `config/project.example.toml` uses a placeholder path and no model bindings; parse/validation success does not mean a live run is configured. Codex fixtures and source evidence constants remain version-specific provenance, not a generic admission standard. The 56 schemas and five SQLite migrations were left unchanged. Local development configuration is distinct from runtime permissions; no credentials or hosted resources were configured.

Public-project gaps: no tracked license or CI configuration exists. The owner must choose a license before promising open-source redistribution rights; a small offline CI gate can be added later. Neither missing item justifies implementing hosted infrastructure or a marketplace now.

Package inspection also found a migration dependency: the built wheel contains only `orchestrator` and distribution metadata, while the current configuration loader resolves shipped presets/configuration relative to the source checkout. Build success therefore does not establish a usable installed configuration CLI. The source distribution includes the untracked `.agents/` installations, skill lock, and local `.codex/` configuration/rule. Keep build outputs local; a later packaging change should explicitly include required runtime resources and exclude local development settings. No package was published, and no packaging behavior was changed in this task.

## Validation and limits

Validation results are recorded below after execution. Passing checks establish a consistent runnable legacy baseline after documentation cleanup; they do not implement or validate the proposed experiment platform, Deep Agents integration, current provider access, or AgentCore hosting.

| Validation performed | Result |
| --- | --- |
| `UV_CACHE_DIR=/private/tmp/agent-lab-cleanup-uv-cache uv run --locked --no-sync pytest -m 'not live'` | **203 passed, 2 live tests deselected**, 18.24 seconds. Includes byte comparisons for all 56 generated schemas. |
| `uv run --locked --no-sync ruff check .` | Passed. |
| `uv run --locked --no-sync ruff format --check .` | Passed; no files reformatted. |
| `uv run --locked --no-sync mypy src` | Passed for all 30 source files. |
| `uv lock --check` | Passed; 20 packages resolved, lock unchanged. |
| `uv build --out-dir /private/tmp/agent-lab-cleanup-audit/dist` | Source distribution and wheel built successfully; archive inspection exposed the packaging limitations above. |
| Existing typed validator on every shipped application/development TOML | All **10** files passed: three configuration files, agent catalog, six workflows. |
| CLI default/help/version | All returned exit 0; reports the current legacy command identity and unavailable run/UI interface. |
| `python3 scripts/check_starter.py` | Supplemental references passed: 16 recursively discovered TOMLs, 11 agents, 6 workflows. |
| `python3 scripts/codex_task.py review --task 'Review the specified diff against AGENTS.md.' --dry-run` | Passed without launching Codex; still a legacy development helper. |
| Documentation paths and inventory coverage | All 29 local Markdown links/anchors resolved; all 143 task-start tracked paths classified exactly once. |
| Deleted-file consumer and stale-instruction scans | No deleted path is consumed by surviving source/tests/scripts/config/presets. Old paths in this audit are historical inventory entries. Remaining old naming/intent is bounded legacy code/config and the explicitly reviewed local rule, not an active roadmap. |
| Byte-hash comparison with task-start snapshot | **132 retained tracked files unchanged**; only README/development guidance rewritten and nine tracked non-code files deleted. All production code, tests, scripts, runtime TOMLs/presets, generated schemas, lock/build metadata, user-modified AGENTS and local Codex configuration preserved. |
| `git diff --check`, final status/diff review | Passed; intentional deletions checked. Changes remain uncommitted; pre-existing modifications/local tooling are separate. No push. |

Checks using uv shared the temporary cache above. No source fix, dependency installation for Deep Agents/AgentCore, persisted schema change, live provider call, AWS deployment, or first experiment was performed. No deleted file had to be restored for the runnable baseline.

## Complete tracked-file inventory

Every task-start tracked path occurs exactly once in this table. Deleted paths are historical inventory entries, not links or instructions to reopen obsolete contracts. Code, tests, runtime configuration and generated schemas classified ADAPT-LATER were retained without edits in this task.

| Tracked path | Classification | Rationale |
| --- | --- | --- |
| `.codex/config.toml` | KEEP | Local development defaults remain useful; preserve the pre-existing user changes to review/network/search settings. |
| `.env.example` | DELETE-NOW | Unused application host/UI/environment template falsely claimed that the CLI automatically loads .env; real Codex environment settings are documented separately. |
| `.gitignore` | KEEP | Correct Python build/cache, environment-secret, and local-data exclusions. |
| `.no-mistakes.yaml` | REVIEW | Optional external review-tool agent selection; no repository consumer or current owner was established. Retain pending tooling review. |
| `.python-version` | KEEP | Python 3.12 remains the supported local toolchain baseline. |
| `AGENTS.md` | KEEP | Current Agent Lab purpose and sole project continuity authority; preserve the pre-existing rewrite byte-for-byte. |
| `README.md` | KEEP | Rewritten to describe Agent Lab intent and the actual surviving legacy implementation without the superseded roadmap. |
| `config/backends.toml` | ADAPT-LATER | Required by the current loader; fake/Codex settings are legacy adapter configuration, not the future generic backend contract. |
| `config/development.toml` | ADAPT-LATER | Required by the current loader and optional launcher; generic development presets may survive after loader separation and ownership review. |
| `config/project.example.toml` | ADAPT-LATER | Required by current validation/tests; old project/workspace/model settings must not become experiment defaults. |
| `docs/DEVELOPMENT.md` | KEEP | Rewritten to retain runnable commands and live-test gates while removing old scope/architecture mandates. |
| `docs/IMPLEMENTATION_PLAN.md` | DELETE-NOW | Superseded coding-workflow product contracts and ten-milestone roadmap contradict the current authority. |
| `docs/INTEGRATION_AUDIT.md` | DELETE-NOW | Completed Codex/runtime integration audit governs the former product; current limits are captured in the new audit. |
| `docs/research/CROSS_RUNTIME_AUTHORITY_REVIEW.md` | DELETE-NOW | Approved architecture for the old admission/ACP workflow is not an accepted Agent Lab requirement. |
| `docs/research/PRE_M6_CODEX_REVIEW.md` | DELETE-NOW | Historical pre-milestone Codex review has no active experiment or implementation role. |
| `docs/research/STOP_CONTROL_SEMANTICS_REVIEW.md` | DELETE-NOW | Old runtime-control candidate research has no active experiment; preserve the useful acknowledgement/outcome distinction in this audit. |
| `presets/agents.toml` | ADAPT-LATER | Eleven old specialist profiles are consumed by the current loader/tests; retire with those consumers rather than prescribe them for Agent Lab. |
| `presets/workflows/debug.toml` | ADAPT-LATER | Consumed debug coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `presets/workflows/feature.toml` | ADAPT-LATER | Consumed feature coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `presets/workflows/handoff.toml` | ADAPT-LATER | Consumed handoff coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `presets/workflows/prototype.toml` | ADAPT-LATER | Consumed prototype coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `presets/workflows/research.toml` | ADAPT-LATER | Consumed research coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `presets/workflows/review.toml` | ADAPT-LATER | Consumed review coding/research workflow fixture; retire with its loader and coordinator regression consumers. |
| `pyproject.toml` | ADAPT-LATER | Keep the runnable build/test toolchain now; later adapt product naming, CLI metadata, and the required Codex dependency together. |
| `schemas/agent-catalog-v1.json` | ADAPT-LATER | Generated agent-catalog-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/agent-run-spec-v1.json` | ADAPT-LATER | Generated agent-run-spec-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/artifact-envelope-v1.json` | ADAPT-LATER | Generated artifact-envelope-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/artifact-manifest-v1.json` | ADAPT-LATER | Generated artifact-manifest-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/artifact-v1.json` | ADAPT-LATER | Generated artifact-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/attempt-result-v1.json` | ADAPT-LATER | Generated attempt-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/attempt-state-v1.json` | ADAPT-LATER | Generated attempt-state-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/backend-capabilities-v1.json` | ADAPT-LATER | Generated backend-capabilities-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/backend-preflight-record-v1.json` | ADAPT-LATER | Generated backend-preflight-record-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/backend-preflight-snapshot-v1.json` | ADAPT-LATER | Generated backend-preflight-snapshot-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/backend-settings-v1.json` | ADAPT-LATER | Generated backend-settings-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/codex-read-only-result-v1.json` | ADAPT-LATER | Generated codex-read-only-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/command-receipt-v1.json` | ADAPT-LATER | Generated command-receipt-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/control-ack-v1.json` | ADAPT-LATER | Generated control-ack-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/control-delivery-v1.json` | ADAPT-LATER | Generated control-delivery-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-acceptance-policy-v1.json` | ADAPT-LATER | Generated decision-acceptance-policy-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-disposition-v1.json` | ADAPT-LATER | Generated decision-disposition-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-engine-failure-v1.json` | ADAPT-LATER | Generated decision-engine-failure-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-evidence-v1.json` | ADAPT-LATER | Generated decision-evidence-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-inference-binding-v1.json` | ADAPT-LATER | Generated decision-inference-binding-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-option-v1.json` | ADAPT-LATER | Generated decision-option-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-question-v1.json` | ADAPT-LATER | Generated decision-question-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-record-v1.json` | ADAPT-LATER | Generated decision-record-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-request-v1.json` | ADAPT-LATER | Generated decision-request-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-result-v1.json` | ADAPT-LATER | Generated decision-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/decision-score-vector-v1.json` | ADAPT-LATER | Generated decision-score-vector-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/development-config-v1.json` | ADAPT-LATER | Generated development-config-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/event-v1.json` | ADAPT-LATER | Generated event-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/handoff-v1.json` | ADAPT-LATER | Generated handoff-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/intervention-record-v1.json` | ADAPT-LATER | Generated intervention-record-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/intervention-v1.json` | ADAPT-LATER | Generated intervention-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/ledger-mutation-v1.json` | ADAPT-LATER | Generated ledger-mutation-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/orchestrator-policy-v1.json` | ADAPT-LATER | Generated orchestrator-policy-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/outbox-action-v1.json` | ADAPT-LATER | Generated outbox-action-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/owner-lease-v1.json` | ADAPT-LATER | Generated owner-lease-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/preflight-context-v1.json` | ADAPT-LATER | Generated preflight-context-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/preflight-fact-v1.json` | ADAPT-LATER | Generated preflight-fact-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/preflight-result-v1.json` | ADAPT-LATER | Generated preflight-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/profile-overlays-v1.json` | ADAPT-LATER | Generated profile-overlays-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/project-config-v1.json` | ADAPT-LATER | Generated project-config-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/reconciliation-v1.json` | ADAPT-LATER | Generated reconciliation-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/reservation-v1.json` | ADAPT-LATER | Generated reservation-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/resolved-decision-question-v1.json` | ADAPT-LATER | Generated resolved-decision-question-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/resolved-orchestrator-policy-v1.json` | ADAPT-LATER | Generated resolved-orchestrator-policy-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/run-spec-v1.json` | ADAPT-LATER | Generated run-spec-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/run-state-v1.json` | ADAPT-LATER | Generated run-state-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/shutdown-receipt-v1.json` | ADAPT-LATER | Generated shutdown-receipt-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/stage-projection-v1.json` | ADAPT-LATER | Generated stage-projection-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/stage-redirect-v1.json` | ADAPT-LATER | Generated stage-redirect-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/stage-result-v1.json` | ADAPT-LATER | Generated stage-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/steer-command-v1.json` | ADAPT-LATER | Generated steer-command-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/worker-event-v1.json` | ADAPT-LATER | Generated worker-event-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/worker-identity-v1.json` | ADAPT-LATER | Generated worker-identity-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/worker-result-v1.json` | ADAPT-LATER | Generated worker-result-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/workflow-overlays-v1.json` | ADAPT-LATER | Generated workflow-overlays-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `schemas/workflow-preset-v1.json` | ADAPT-LATER | Generated workflow-preset-v1 legacy contract; retained unchanged for schema-registry and byte-comparison consumers; adapt/retire with owning models. |
| `scripts/check_starter.py` | ADAPT-LATER | Active supplemental cross-reference check but assumes old specialists/workflow stages and recursively scans TOML; retire or narrow with the loader. |
| `scripts/codex_task.py` | ADAPT-LATER | Optional generic development launcher, coupled to development.toml and explicit Codex execution settings; no project-continuity authority. |
| `scripts/export_schemas.py` | ADAPT-LATER | Working exporter for legacy models; retain until the owning schema registry is replaced. |
| `src/orchestrator/__init__.py` | ADAPT-LATER | Legacy package identity/version and orchestration module documentation; rename only with packaging consumers. |
| `src/orchestrator/__main__.py` | ADAPT-LATER | Legacy CLI entry point; migrate with package naming and command tests. |
| `src/orchestrator/artifacts/__init__.py` | ADAPT-LATER | Artifact API exports tied to the current store; migrate with storage ownership contracts. |
| `src/orchestrator/artifacts/store.py` | ADAPT-LATER | Useful streaming hashes, atomic rename and verified reads; requires legacy attempt/ledger ownership and publication types. |
| `src/orchestrator/backends/__init__.py` | ADAPT-LATER | Legacy worker-adapter package surface; retain until adapter decisions are reviewed. |
| `src/orchestrator/backends/codex.py` | ADAPT-LATER | Public re-export for the pinned Codex adapter; retain or remove with the optional comparison backend. |
| `src/orchestrator/backends/codex_backend.py` | ADAPT-LATER | Large pinned read-only provider/host policy adapter; optional future baseline, not required new infrastructure. |
| `src/orchestrator/backends/codex_bridge.py` | ADAPT-LATER | Codex Unix socket/stdio bridge; only justified with that process-owner adapter. |
| `src/orchestrator/backends/codex_output.py` | ADAPT-LATER | Validated bounded exact-byte report retention; useful technique but tightly linked to old run/attempt/ledger contracts. |
| `src/orchestrator/backends/codex_owner.py` | ADAPT-LATER | Provider-specific local process-group and bridge settlement; no proof of detached/remote effect settlement or hosted-runtime compatibility. |
| `src/orchestrator/backends/decision.py` | ADAPT-LATER | Model-free first-allowed baseline for bounded decisions; selectively reuse if a decision experiment needs it. |
| `src/orchestrator/backends/fake.py` | ADAPT-LATER | Deterministic scripts/barriers/manual clock are reusable testing ideas; current methods require worker and attempt contracts. |
| `src/orchestrator/backends/fake_decision.py` | ADAPT-LATER | Controllable asynchronous decision replies; retain only with a bounded-decision experiment/test seam. |
| `src/orchestrator/backends/protocol.py` | ADAPT-LATER | SDK-independent protocol, but its AgentRunSpec and lifecycle requirements still encode old runtime assumptions. |
| `src/orchestrator/cli.py` | ADAPT-LATER | Runnable validation CLI; product name and stale Milestone 3 message await code migration. |
| `src/orchestrator/config.py` | ADAPT-LATER | Typed TOML/error handling reusable; shipped loader hardcodes old paths and exactly six workflows. |
| `src/orchestrator/domain/__init__.py` | ADAPT-LATER | Generic dependency direction is sound, but exported domain remains the old product. |
| `src/orchestrator/domain/backend.py` | ADAPT-LATER | Useful capability/failure/usage vocabulary; handles and reconciliation are tied to worker attempts and session/thread/turn ownership. |
| `src/orchestrator/domain/decisions.py` | ADAPT-LATER | Useful evidence/inference identity, score semantics, abstention and deterministic validation; action configuration is old stage redirection. |
| `src/orchestrator/domain/models.py` | ADAPT-LATER | Closed coding roles/stages/conditions, profile bindings, worktree rules, controls/events and Codex config obstruct generic experiments. |
| `src/orchestrator/execution/__init__.py` | ADAPT-LATER | Legacy coordinator exports; retire together with the scheduler. |
| `src/orchestrator/execution/coordinator.py` | ADAPT-LATER | 4,058-line workflow scheduler/control/recovery engine; external harness/runtime should replace its role after reviewed retirement. |
| `src/orchestrator/persistence/__init__.py` | ADAPT-LATER | Public exports of old ledger/models/ownership; retire with consumer migration. |
| `src/orchestrator/persistence/ledger.py` | ADAPT-LATER | 2,065-line transactional workflow ledger; reuse integrity/idempotency techniques, not all domain tables or mutation machinery. |
| `src/orchestrator/persistence/migrations.py` | ADAPT-LATER | Five active legacy migrations; preserve until the data/compatibility decision, never repurpose existing rows silently. |
| `src/orchestrator/persistence/models.py` | ADAPT-LATER | Typed storage commands/projections are deeply coupled to attempts, stages, controls, decisions and outbox/reservations. |
| `src/orchestrator/persistence/ownership.py` | ADAPT-LATER | Single local coordinator Unix fcntl lock/generation; no generic distributed/session ownership abstraction. |
| `src/orchestrator/resolution.py` | ADAPT-LATER | Pure canonical snapshot hashing is useful; the resolver itself assumes fixed specialist profiles/workflow slots and permissions. |
| `src/orchestrator/schemas.py` | ADAPT-LATER | Registry exports 56 active legacy contracts; retire/add schemas only with reviewed consumer changes. |
| `src/orchestrator/validation.py` | ADAPT-LATER | Useful strict input, reference, policy and permission checks, but workflow-path/topology/verification rules are product-specific. |
| `tasks/01-foundation.md` | DELETE-NOW | Completed or superseded previous-orchestrator milestone instructions; no current Agent Lab task authority. |
| `tasks/06b-cross-runtime-authority-policy.md` | DELETE-NOW | Completed or superseded previous-orchestrator milestone instructions; no current Agent Lab task authority. |
| `tasks/06c-codex-interrupt-correctness.md` | DELETE-NOW | Completed or superseded previous-orchestrator milestone instructions; no current Agent Lab task authority. |
| `tests/conftest.py` | ADAPT-LATER | Session fixtures load all old shipped configs; decouple before removing preset/config files. |
| `tests/fixtures/backends/codex-alternate-ownership.json` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/backends/codex-authority-policy-0.159.2.json` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/backends/codex-config-read-0.159.2.json` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/backends/codex-features-list-0.159.2.txt` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/backends/codex-read-only-result-v1.json` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/backends/codex-sdk-0.159.2.json` | ADAPT-LATER | Active offline Codex version/policy/output evidence fixture; retain or retire with the provider-specific adapter/tests, not as a generic interface standard. |
| `tests/fixtures/decisions/deterministic-policy.json` | ADAPT-LATER | Active dynamically selected offline decision fixture; supports normalization tests, not measured performance of a live inference mechanism. |
| `tests/fixtures/decisions/general-llm-readout.json` | ADAPT-LATER | Active dynamically selected offline decision fixture; supports normalization tests, not measured performance of a live inference mechanism. |
| `tests/fixtures/decisions/generative-structured-output.json` | ADAPT-LATER | Active dynamically selected offline decision fixture; supports normalization tests, not measured performance of a live inference mechanism. |
| `tests/fixtures/decisions/native-decision-model.json` | ADAPT-LATER | Active dynamically selected offline decision fixture; supports normalization tests, not measured performance of a live inference mechanism. |
| `tests/fixtures/invalid/out-of-bounds-slot.toml` | ADAPT-LATER | Active rejected-overlay/effort fixture; retain current negative tests, then translate only useful validation properties. |
| `tests/fixtures/invalid/permission-widening.toml` | ADAPT-LATER | Active rejected-overlay/effort fixture; retain current negative tests, then translate only useful validation properties. |
| `tests/fixtures/invalid/unknown-overlay-profile.toml` | ADAPT-LATER | Active rejected-overlay/effort fixture; retain current negative tests, then translate only useful validation properties. |
| `tests/fixtures/invalid/unsupported-effort.toml` | ADAPT-LATER | Active rejected-overlay/effort fixture; retain current negative tests, then translate only useful validation properties. |
| `tests/test_cli_and_schemas.py` | ADAPT-LATER | Protects present CLI identity and byte-for-byte generated-schema consistency; migrate with command/contract owners. |
| `tests/test_codex_backend.py` | ADAPT-LATER | Offline preflight, authority/output and coordinator integration coverage; only needed with retained Codex backend. |
| `tests/test_codex_backend_lifecycle.py` | ADAPT-LATER | Offline SDK/owner fakes protect exact identities, ACK/terminal/settlement separation, policy drift and uncertain delivery. |
| `tests/test_codex_backend_live.py` | ADAPT-LATER | Two explicit opt-in provider tests; preserve gates if Codex remains. No live call was made in this task. |
| `tests/test_codex_owner.py` | ADAPT-LATER | Local process-owner probes; useful only if that adapter survives, not evidence of cloud/remote-effect settlement. |
| `tests/test_config_and_validation.py` | ADAPT-LATER | Reusable strictness/reference/permission properties mixed with obsolete six-workflow and verification-topology assertions. |
| `tests/test_decisions.py` | ADAPT-LATER | Evidence freshness, calibration/semantics, abstention and scripted barriers are reusable; no live decision-model evaluation is established. |
| `tests/test_execution_coordinator.py` | ADAPT-LATER | Mostly old workflow/repair/scheduler/control regressions; preserve selected failure/idempotency properties at future adapter seams before retirement. |
| `tests/test_fake_backend.py` | ADAPT-LATER | Reusable explicit barriers/manual-clock behavior, currently asserted through the old WorkerBackend. |
| `tests/test_persistence_ledger.py` | ADAPT-LATER | Mixes reusable rollback/immutability/artifact integrity/reopen checks with obsolete projection/outbox/reservation/control behavior. |
| `tests/test_resolution.py` | ADAPT-LATER | Reusable immutable/canonical identity and permission narrowing mixed with workflow-specific binding/slot/overlay assertions. |
| `uv.lock` | ADAPT-LATER | Current pinned reproducibility baseline; update deliberately when dependencies/package metadata change, not during documentation cleanup. |

## Review decisions and next task

Review the optional Codex comparison backend, existing-data compatibility/export requirement, first controlled workload and small persisted experiment contracts, package naming, license choice, and ownership of optional local tooling. These do not block completion of this documentation-only cleanup. Destructive code/schema/preset retirement requires a later reviewed implementation scope.

The exact proposed next implementation task is **the smallest offline experiment-to-result slice after contract review**: versioned provider-independent definition/run/evaluation/artifact records, deterministic resolution, one fake invocation, immutable provenance, verified output bytes, failure records, and a local rerun entry point. Preserve the current regression baseline. Do not install Deep Agents/AgentCore, run live models, delete the old runtime, or modify old databases in that first slice. See the staged gates in [CODEBASE_MIGRATION_PLAN.md](CODEBASE_MIGRATION_PLAN.md).
