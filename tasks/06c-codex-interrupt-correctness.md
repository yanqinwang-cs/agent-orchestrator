# Milestone 6 follow-up — Codex interrupt correctness

## Scope

Correct the pinned `openai-codex==0.159.2` exact-turn interrupt mapping and deterministic coverage. Preserve the existing `interrupt` / `close` / `inspect` boundary, exact attempt/thread/turn target, fail-closed unknown outcomes and independent owner settlement. Do not add force-stop escalation, a generic cancellation model, schema migration, ACP or M7 work.

## Implementation

- Treat a successful, request-correlated `turn_interrupt(thread_id, turn_id)` call as a control acknowledgement. Pinned `TurnInterruptResponse` is empty `{}`; no echoed `turn_id` is expected and no terminal outcome is inferred from the empty response.
- Make the offline fake and SDK fixture use the empty response shape. Preserve accepted/rejected command deduplication and prevent stale/foreign handles from reaching the SDK.
- Preserve bounded rejection diagnostics from public SDK exception class/code and a safe category (`no_active_turn`, `active_turn_mismatch`, `thread_unavailable`, `submission_failure`, or `provider_rejection`). Include the adapter-owned target, stage and elapsed time; omit raw provider message/data.
- Cover ACK plus interrupted terminal, ACK plus normal completion, rejection plus later interrupted observation, response loss/caller cancellation, duplicate commands and unsettled close. Reconcile a settled `FailureClass.CANCELLED` as `AttemptStatus.CANCELLED`.
- Persist the control ACK event before bounded close. If close is unsettled, append an UNKNOWN delivery event, retain the target and reservations, and do not rewrite the earlier ACK.
- Gate the live control test on an exact-turn `turn/started` or `item/started` notification. A completion after ACK remains a valid normal-completion race.

## Validation

- Offline: 203 passed, 2 live tests deselected.
- Ruff check and format, mypy, `uv lock --check`, all three prescribed config validations passed.
- Schema export completed with no schema diff.
- Read-only live smoke passed on SDK/CLI 0.159.2 with `gpt-5.6-luna` and default `high` effort.
- Exact-turn live control passed after observed activity: exact RPC ACK accepted, terminal state `interrupted`, independent owner receipt settled with child reaped, process group empty and bridge disconnected.

The immediate post-`turn/start` probes returned sanitized `InvalidRequestError` code `-32600`, category `no_active_turn`, while same-owner inspection reported the exact turn `running`. Waiting for the pinned runtime's exact-turn activity notification resolved this readiness race without retargeting.

## Remaining M6 limitation

The generation-bound receipt establishes the app-server child, its process group and the SDK bridge. It does not establish that every Codex-managed command descendant remained in that group or that remote inference/effects settled. M6 remains incomplete until this ownership/effect coverage is established or its scope is explicitly resolved. No process-tree containment, remote-effect ledger or wider settlement claim is introduced here.
