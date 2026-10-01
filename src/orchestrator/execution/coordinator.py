"""Bounded execution for immutable workflow snapshots and normalized workers."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from typing import Any, Literal, cast
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import ValidationError

from orchestrator.backends.fake import FakeClock
from orchestrator.backends.protocol import KnownPrelaunchFailure, WorkerBackend
from orchestrator.domain.backend import (
    ArtifactEntry,
    BackendPreflightSnapshot,
    ControlAck,
    OutputStatus,
    PreflightContext,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerDisconnectedEvent,
    WorkerEvent,
    WorkerEventKind,
    WorkerFailureEvent,
    WorkerHandle,
    WorkerIdentity,
    WorkerProgressEvent,
    WorkerResult,
    WorkerStartedEvent,
    WorkerTerminalEvent,
    derive_lifecycle_owner_id,
)
from orchestrator.domain.decisions import (
    DecisionDisposition,
    DecisionDispositionReason,
    DecisionDispositionStatus,
    DecisionEngine,
    DecisionEngineFailure,
    DecisionEngineReply,
    DecisionEvidence,
    DecisionFailureClass,
    DecisionMechanism,
    DecisionOption,
    DecisionPolicyAction,
    DecisionRequest,
    DecisionResult,
    DecisionResultClass,
    decision_request_hash,
    decision_result_hash,
    evaluate_decision,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    AttemptState,
    AttemptStatus,
    BackendPreflightRecordedEvent,
    BackendPreparationIntentRecordedEvent,
    Condition,
    DecisionLifecycleEvent,
    Event,
    EventKind,
    FailureClass,
    InputEntry,
    Intervention,
    InterventionKind,
    InterventionLifecycleEvent,
    InterventionRequestedEvent,
    InterventionTargetScope,
    OutboxStatus,
    PauseIntervention,
    RedirectIntervention,
    ResolvedDecisionQuestion,
    ResolvedProfile,
    ResolvedStage,
    ResumeIntervention,
    RetryIntervention,
    RunStatus,
    RunStatusChangedEvent,
    SlotKind,
    StageCompletion,
    StageKind,
    StageStatus,
    StageStatusChangedEvent,
    SteerIntervention,
    StopAttemptIntervention,
    StopIntervention,
    TimeoutDetectedEvent,
)
from orchestrator.persistence.ledger import (
    CommandIdConflict,
    LedgerInvariantError,
    ReservationConflict,
    SQLiteLedger,
    canonical_json,
    content_hash,
)
from orchestrator.persistence.models import (
    AttemptRegistration,
    AttemptResultRegistration,
    BackendPreflightRecord,
    CommandOutcome,
    CommandReceipt,
    ControlDelivery,
    ControlDeliveryStatus,
    DecisionRecord,
    InterventionRecord,
    LedgerMutation,
    OutboxAction,
    OutboxIntent,
    OutboxOutcomeChange,
    PersistedAttempt,
    PersistedRun,
    ReservationChange,
    ReservationOperation,
    RunProjectionUpdate,
    StageRedirect,
    StageResult,
    StageUpdate,
)
from orchestrator.persistence.ownership import CoordinatorOwnership

_ACTIVE_ATTEMPT_STATES = {
    AttemptStatus.LAUNCHING,
    AttemptStatus.RUNNING,
    AttemptStatus.CANCEL_REQUESTED,
    AttemptStatus.OUTCOME_UNKNOWN,
}
_SUCCESSFUL_STAGE_STATES = {StageStatus.SUCCEEDED, StageStatus.SKIPPED}
_TERMINAL_RUN_STATES = {
    RunStatus.SUCCEEDED,
    RunStatus.FAILED,
    RunStatus.STOPPED,
    RunStatus.ATTENTION_REQUIRED,
}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
type DecisionEventKind = Literal[
    EventKind.DECISION_REQUESTED,
    EventKind.DECISION_INFERENCE_STARTED,
    EventKind.DECISION_RESULT_RECORDED,
    EventKind.DECISION_INFERENCE_FAILED,
    EventKind.DECISION_RESULT_REJECTED,
    EventKind.DECISION_RESULT_STALE,
    EventKind.DECISION_RESULT_DISALLOWED,
    EventKind.DECISION_ABSTAINED,
    EventKind.DECISION_POLICY_EVALUATED,
    EventKind.DECISION_ACCEPTED,
    EventKind.DECISION_FALLBACK,
    EventKind.DECISION_ATTENTION_REQUIRED,
]


class InputResolutionError(ValueError):
    """A declared stage input is absent from the persisted run evidence."""


def resolve_stage_slots(
    run: PersistedRun,
    stage: ResolvedStage,
    *,
    redirected_profile_id: str | None = None,
) -> tuple[tuple[str, str], ...]:
    """Return stable slot/profile pairs from the already frozen run selection."""
    if stage.kind != StageKind.WORKER:
        return ()
    selection = next((item for item in run.spec.selections if item.stage_id == stage.id), None)
    if selection is None:
        raise LedgerInvariantError(f"resolved workflow has no slot selection for {stage.id}")
    if selection.worker_count != len(selection.profile_ids):
        raise LedgerInvariantError(f"resolved slot count does not match profiles for {stage.id}")
    if stage.min_workers is None or stage.max_workers is None:
        raise LedgerInvariantError(f"worker stage {stage.id} has no declared slot bounds")
    if not stage.min_workers <= selection.worker_count <= stage.max_workers:
        raise LedgerInvariantError(f"resolved slot count exceeds declared bounds for {stage.id}")
    if (
        selection.worker_count != stage.min_workers
        and not run.spec.workflow.policy.allow_count_selection
    ):
        raise LedgerInvariantError(f"workflow policy forbids count selection for {stage.id}")
    if (
        stage.slot_kind == SlotKind.SELECT_ONE
        and stage.default_profile is not None
        and selection.profile_ids[0] != stage.default_profile
        and not run.spec.workflow.policy.allow_profile_selection
    ):
        raise LedgerInvariantError(f"workflow policy forbids profile selection for {stage.id}")
    profile_ids = selection.profile_ids
    if redirected_profile_id is not None:
        if stage.slot_kind != SlotKind.SELECT_ONE or len(profile_ids) != 1:
            raise LedgerInvariantError(f"redirected stage {stage.id} is not select-one")
        profile_ids = (redirected_profile_id,)
    result: list[tuple[str, str]] = []
    for index, profile_id in enumerate(profile_ids, start=1):
        if (
            profile_id not in stage.allowed_profiles
            or profile_id not in run.spec.workflow.allowed_profiles
        ):
            raise LedgerInvariantError(
                f"resolved profile {profile_id} is outside the allowlist for {stage.id}"
            )
        result.append((f"{stage.id}/slot-{index:02d}", profile_id))
    return tuple(result)


def evaluate_condition(stage: ResolvedStage, repair_decision: str | None) -> bool | None:
    """Evaluate the closed v1 condition vocabulary; None means its gate is pending."""
    if stage.when == Condition.ALWAYS:
        return True
    if repair_decision is None:
        return None
    if stage.when == Condition.REPAIR_NEEDED:
        return repair_decision == "repair_needed"
    if stage.when == Condition.REPAIR_NOT_NEEDED:
        return repair_decision == "repair_not_needed"
    raise LedgerInvariantError(f"unsupported stage condition {stage.when}")


def resolve_stage_inputs(
    run: PersistedRun,
    stage: ResolvedStage,
    *,
    repair_decision: str | None = None,
) -> tuple[tuple[InputEntry, ...], str | None]:
    """Resolve task, project baseline, upstream outputs and declared branch outputs."""
    stage_by_id = {item.stage_id: item for item in run.stages}
    stage_defs = {item.id: item for item in run.spec.workflow.stages}
    project_revision = content_hash(
        canonical_json(
            {
                "project_id": run.spec.project.project_id,
                "settings_revision": run.spec.project.settings_revision,
                "run_snapshot_hash": run.spec.snapshot_hash,
            }
        )
    )
    branch_map = {branch: dict(outputs) for branch, outputs in run.spec.workflow.branch_outputs}
    workspace_revisions: list[str] = []
    entries: list[InputEntry] = []

    for input_name in stage.inputs:
        source = input_name
        if input_name == "task":
            digest = content_hash(run.spec.task)
        elif input_name == "project.revision":
            digest = project_revision
            workspace_revisions.append(digest)
        else:
            if input_name.startswith("selected."):
                if repair_decision is None:
                    raise InputResolutionError(f"{stage.id}: branch decision is not available")
                output_name = input_name.partition(".")[2]
                source = branch_map.get(repair_decision, {}).get(output_name, "")
                if not source:
                    raise InputResolutionError(
                        f"{stage.id}: {input_name} has no declared mapping for {repair_decision}"
                    )
            upstream_stage, separator, output_name = source.partition(".")
            if not separator or upstream_stage not in stage_defs:
                raise InputResolutionError(f"{stage.id}: unsupported input {input_name!r}")
            projection = stage_by_id.get(upstream_stage)
            if projection is None or projection.status != StageStatus.SUCCEEDED:
                raise InputResolutionError(f"{stage.id}: required input {source} is unavailable")
            if projection.result is None:
                raise InputResolutionError(f"{stage.id}: required output {source} is missing")
            outputs = tuple(item for item in projection.result.outputs if item.name == output_name)
            if not outputs:
                raise InputResolutionError(f"{stage.id}: required output {source} is missing")
            digest = content_hash(canonical_json(outputs))
            if projection.result.workspace_revision:
                workspace_revisions.append(projection.result.workspace_revision)
        entries.append(
            InputEntry(
                name=input_name,
                content_hash=digest,
                source=source,
                reason="resolved from immutable run input or completed upstream evidence",
            )
        )

    unique_revisions = tuple(dict.fromkeys(workspace_revisions))
    workspace_revision = unique_revisions[0] if len(unique_revisions) == 1 else None
    return tuple(entries), workspace_revision


class ExecutionCoordinator:
    """Deterministic workflow scheduler using ledger transactions and a worker adapter."""

    def __init__(
        self,
        ledger: SQLiteLedger,
        backend: WorkerBackend,
        ownership: CoordinatorOwnership,
        *,
        clock: FakeClock | None = None,
        global_parallelism: int = 4,
        actor: str = "coordinator",
        control_timeout_seconds: float = 5.0,
        decision_engine: DecisionEngine | None = None,
        decision_timeout_seconds: float = 30.0,
        preflight_timeout_seconds: float = 30.0,
        launch_timeout_seconds: float = 30.0,
    ) -> None:
        if global_parallelism < 1:
            raise ValueError("global_parallelism must be positive")
        if ownership.lease is None:
            raise ValueError("coordinator ownership must be acquired before execution")
        if control_timeout_seconds <= 0:
            raise ValueError("control_timeout_seconds must be positive")
        if decision_timeout_seconds <= 0:
            raise ValueError("decision_timeout_seconds must be positive")
        if preflight_timeout_seconds <= 0 or launch_timeout_seconds <= 0:
            raise ValueError("backend preflight and launch timeouts must be positive")
        self.ledger = ledger
        self.backend = backend
        self.ownership = ownership
        self.clock = clock or FakeClock(origin=datetime.now(UTC))
        self.global_parallelism = global_parallelism
        self.actor = actor
        self.control_timeout_seconds = control_timeout_seconds
        self.decision_engine = decision_engine
        self.decision_timeout_seconds = decision_timeout_seconds
        self.preflight_timeout_seconds = preflight_timeout_seconds
        self.launch_timeout_seconds = launch_timeout_seconds
        self._elapsed_origins: dict[str, tuple[float, float]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}

    def advance(self, run_id: str) -> bool:
        """Persist deterministic stage transitions and launch intents until quiescent."""
        changed_any = False
        for _ in range(10_000):
            run = self.ledger.get_run(run_id)
            if run.state.status in _TERMINAL_RUN_STATES:
                return changed_any
            if run.state.status in {RunStatus.PAUSED, RunStatus.STOPPED}:
                return changed_any
            if run.state.status == RunStatus.PAUSE_REQUESTED:
                if not self._run_has_owned_attempt(run_id):
                    self._set_run_status(run, RunStatus.PAUSED, "active workers drained")
                    return True
                return changed_any
            if run.state.status == RunStatus.STOPPING:
                if not self._run_has_owned_attempt(run_id):
                    self._set_run_status(run, RunStatus.STOPPED, "worker ownership settled")
                    return True
                return changed_any
            self._remember_elapsed_origin(run)
            if self._elapsed(run) >= run.spec.workflow.max_duration_seconds:
                self._expire_run(run)
                return True
            stage_by_id = {item.stage_id: item for item in run.stages}
            failed_stage = next(
                (item for item in run.stages if item.status == StageStatus.FAILED), None
            )
            blocked_stage = next(
                (item for item in run.stages if item.status == StageStatus.BLOCKED), None
            )
            if failed_stage is not None:
                self._set_run_status(run, RunStatus.FAILED, f"stage {failed_stage.stage_id} failed")
                return True
            if blocked_stage is not None:
                self._set_run_status(
                    run, RunStatus.ATTENTION_REQUIRED, f"stage {blocked_stage.stage_id} is blocked"
                )
                return True

            repair_gate = stage_by_id.get("repair_gate")
            repair_decision = (
                repair_gate.result.decision
                if repair_gate is not None and repair_gate.result is not None
                else None
            )

            progressed = False
            for stage in run.spec.workflow.stages:
                projection = stage_by_id[stage.id]
                if projection.status in {
                    StageStatus.SUCCEEDED,
                    StageStatus.SKIPPED,
                    StageStatus.FAILED,
                    StageStatus.BLOCKED,
                }:
                    continue
                dependency_states = [stage_by_id[item].status for item in stage.depends_on]
                if any(state == StageStatus.FAILED for state in dependency_states):
                    self._set_run_status(run, RunStatus.FAILED, f"dependency of {stage.id} failed")
                    return True
                if any(state not in _SUCCESSFUL_STAGE_STATES for state in dependency_states):
                    continue

                condition = evaluate_condition(stage, repair_decision)
                if condition is None:
                    continue
                if not condition:
                    if not stage.optional or not run.spec.workflow.policy.allow_optional_skip:
                        self._update_stage(
                            run,
                            StageUpdate(stage_id=stage.id, status=StageStatus.BLOCKED),
                            status=RunStatus.ATTENTION_REQUIRED,
                            reason=f"policy does not permit skipping {stage.id}",
                        )
                        return True
                    self._update_stage(
                        run,
                        StageUpdate(stage_id=stage.id, status=StageStatus.SKIPPED),
                    )
                    changed_any = progressed = True
                    break

                if stage.kind == StageKind.WORKER:
                    try:
                        resolve_stage_inputs(run, stage, repair_decision=repair_decision)
                    except InputResolutionError as error:
                        self._update_stage(
                            run,
                            StageUpdate(stage_id=stage.id, status=StageStatus.BLOCKED),
                            status=RunStatus.ATTENTION_REQUIRED,
                            reason=str(error),
                        )
                        return True
                    if projection.status == StageStatus.PENDING:
                        self._update_stage(
                            run,
                            StageUpdate(stage_id=stage.id, status=StageStatus.READY),
                            status=RunStatus.RUNNING,
                        )
                        changed_any = progressed = True
                        break
                    if projection.status in {StageStatus.READY, StageStatus.RUNNING}:
                        try:
                            made_attempt = self._schedule_one_slot(
                                run, stage, repair_decision=repair_decision
                            )
                        except ReservationConflict:
                            made_attempt = False
                        if made_attempt:
                            changed_any = progressed = True
                            break
                        if self._stage_has_only_settled_slots(run, stage):
                            self._complete_worker_stage(run, stage)
                            changed_any = progressed = True
                            break
                elif projection.status == StageStatus.PENDING:
                    if stage.kind == StageKind.REPAIR_GATE:
                        self._complete_repair_gate(run, stage)
                    else:
                        self._complete_integration_stage(run, stage, repair_decision)
                    changed_any = progressed = True
                    break

            if progressed:
                continue

            refreshed = self.ledger.get_run(run_id)
            if all(item.status in _SUCCESSFUL_STAGE_STATES for item in refreshed.stages):
                self._complete_run(refreshed)
                return True
            return changed_any
        raise RuntimeError("coordinator exceeded its deterministic transition bound")

    async def dispatch_pending(self, run_id: str | None = None) -> int:
        """Claim and start pending outbox actions; event streams run concurrently."""
        actions = []
        owner_id = self.ownership.lease.owner_id if self.ownership.lease else self.actor
        while True:
            action = self.ledger.claim_next_outbox(owner_id, self._now(), run_id=run_id)
            if action is None:
                break
            actions.append(action)
        if not actions:
            return 0
        results = await asyncio.gather(*(self._dispatch_action(action) for action in actions))
        return sum(results)

    async def _dispatch_action(self, action: OutboxAction) -> int:
        if action.kind != "launch_attempt":
            await self._dispatch_control_action(action)
            return 0
        attempt_id = str(action.payload.get("attempt_id", ""))
        attempt = self.ledger.get_attempt(attempt_id)
        if self._inhibits_launches(self.ledger.get_run(action.run_id).state.status):
            self._cancel_unlaunched_action(action, attempt, "run control inhibited launch")
            return 0
        preflight = None
        try:
            if self._requires_backend_preflight_record():
                attempt = self._ensure_backend_preparation_intent(action, attempt)
            context = self._preflight_context(action, attempt)
            preflight = await asyncio.wait_for(
                self.backend.preflight(attempt.spec, context),
                timeout=self.preflight_timeout_seconds,
            )
            preflight_record = None
            if preflight.snapshot is not None:
                if preflight.snapshot.preparation_id != context.preparation_id:
                    if self._requires_backend_preflight_record():
                        self._mark_unknown_launch(
                            action.action_id,
                            self.ledger.get_attempt(attempt_id),
                            "Codex preflight snapshot preparation identity does not match",
                        )
                        return 0
                    raise KnownPrelaunchFailure(
                        FailureClass.CONFIGURATION,
                        "backend preflight snapshot belongs to another preparation",
                        safe_to_retry=False,
                    )
                if (
                    self._requires_backend_preflight_record()
                    and (preflight.accepted or preflight.prepared_handle is not None)
                    and (
                        preflight.snapshot.owner_id != context.lifecycle_owner_id
                        or (
                            preflight.prepared_handle is not None
                            and preflight.prepared_handle.lifecycle_owner_id
                            != context.lifecycle_owner_id
                        )
                    )
                ):
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        "Codex prepared owner does not match its committed lifecycle owner intent",
                    )
                    return 0
                preflight_record = self._persist_backend_preflight(
                    action,
                    attempt,
                    context,
                    preflight.accepted,
                    preflight.snapshot,
                    preflight.prepared_handle,
                )
            elif self._requires_backend_preflight_record():
                raise KnownPrelaunchFailure(
                    FailureClass.CONFIGURATION,
                    "Codex preflight did not provide an immutable effective snapshot",
                    safe_to_retry=False,
                )
            if not preflight.accepted:
                issue = "; ".join(item.message for item in preflight.issues) or "preflight rejected"
                if preflight.prepared_handle is not None:
                    try:
                        cleanup = await asyncio.wait_for(
                            self.backend.close(preflight.prepared_handle),
                            timeout=self._shutdown_grace_seconds(),
                        )
                    except Exception as error:
                        self._mark_unknown_launch(
                            action.action_id,
                            self.ledger.get_attempt(attempt_id),
                            f"rejected preparation cleanup is unknown: {type(error).__name__}",
                        )
                        return 0
                    if not cleanup.settled:
                        self._mark_unknown_launch(
                            action.action_id,
                            self.ledger.get_attempt(attempt_id),
                            cleanup.detail or "rejected preparation cleanup is unsettled",
                        )
                        return 0
                self._settle_launch_failure(
                    action.action_id,
                    self.ledger.get_attempt(attempt_id),
                    FailureClass.CONFIGURATION,
                    issue,
                    safe_to_retry=False,
                )
                return 0
            if self._inhibits_launches(self.ledger.get_run(action.run_id).state.status):
                if preflight.prepared_handle is not None:
                    cleanup = await asyncio.wait_for(
                        self.backend.close(preflight.prepared_handle),
                        timeout=self._shutdown_grace_seconds(),
                    )
                    if not cleanup.settled:
                        self._mark_unknown_launch(
                            action.action_id,
                            self.ledger.get_attempt(attempt_id),
                            cleanup.detail or "prepared launch cleanup is unsettled",
                        )
                        return 0
                self._cancel_unlaunched_action(
                    action,
                    self.ledger.get_attempt(attempt_id),
                    "run control inhibited launch after preflight",
                )
                return 0
            if self._requires_backend_preflight_record():
                prepared = preflight.prepared_handle
                if preflight_record is None or not preflight_record.accepted:
                    raise KnownPrelaunchFailure(
                        FailureClass.CONFIGURATION,
                        "Codex turn start requires its committed accepted snapshot",
                        safe_to_retry=False,
                    )
                if prepared is None:
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        "Codex preflight omitted its prepared owner identity",
                    )
                    return 0
                if (
                    prepared.attempt_id != attempt_id
                    or prepared.backend != attempt.spec.backend
                    or prepared.lifecycle_owner_id != preflight_record.snapshot.owner_id
                ):
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        "Codex prepared owner does not match its immutable snapshot",
                    )
                    return 0
                if prepared.turn_id is not None:
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        "Codex preflight reported a turn before committed turn submission",
                    )
                    return 0
                if prepared.thread_id is None:
                    raise KnownPrelaunchFailure(
                        FailureClass.CONFIGURATION,
                        "Codex preflight did not create a correlated fresh thread",
                        safe_to_retry=False,
                    )
            if preflight_record is not None:
                start_call = self.backend.start(
                    attempt.spec,
                    preflight_record_id=preflight_record.record_id,
                    preflight_record_hash=preflight_record.record_hash,
                )
            else:
                start_call = self.backend.start(attempt.spec)
            handle = await asyncio.wait_for(start_call, timeout=self.launch_timeout_seconds)
        except KnownPrelaunchFailure as error:
            if (
                self._requires_backend_preflight_record()
                and preflight is not None
                and preflight.prepared_handle is not None
            ):
                try:
                    cleanup = await asyncio.wait_for(
                        self.backend.close(preflight.prepared_handle),
                        timeout=self._shutdown_grace_seconds(),
                    )
                except Exception as cleanup_error:
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        "known prelaunch failure cleanup is unknown: "
                        f"{type(cleanup_error).__name__}",
                    )
                    return 0
                if not cleanup.settled:
                    self._mark_unknown_launch(
                        action.action_id,
                        self.ledger.get_attempt(attempt_id),
                        cleanup.detail or "known prelaunch failure cleanup is unsettled",
                    )
                    return 0
            elif self._requires_backend_preflight_record():
                self._mark_unknown_launch(
                    action.action_id,
                    self.ledger.get_attempt(attempt_id),
                    "Codex prelaunch failure did not provide owner cleanup evidence",
                )
                return 0
            self._settle_launch_failure(
                action.action_id,
                self.ledger.get_attempt(attempt_id),
                error.failure_class,
                str(error),
                safe_to_retry=error.safe_to_retry,
            )
            return 0
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                raise
            self._mark_unknown_launch(
                action.action_id,
                self.ledger.get_attempt(attempt_id),
                f"launch outcome is unknown: {type(error).__name__}",
            )
            return 0

        try:
            self._acknowledge_launch(action.action_id, attempt, handle)
        except BaseException as error:
            if isinstance(error, asyncio.CancelledError):
                raise
            self._mark_unknown_launch(
                action.action_id,
                self.ledger.get_attempt(attempt_id),
                f"launch acknowledgement could not be persisted: {type(error).__name__}",
            )
            return 0
        task = asyncio.create_task(self._consume(attempt_id, handle))
        self._workers[attempt_id] = task
        task.add_done_callback(partial(self._worker_done, attempt_id))
        return 1

    def _shutdown_grace_seconds(self) -> float:
        settings = getattr(self.backend, "settings", None)
        configured = getattr(settings, "shutdown_grace_seconds", None)
        return float(configured if configured is not None else self.control_timeout_seconds)

    def _requires_backend_preflight_record(self) -> bool:
        return bool(getattr(self.backend, "requires_preflight_record", False))

    def _preflight_context(
        self, action: OutboxAction, attempt: PersistedAttempt
    ) -> PreflightContext:
        run = self.ledger.get_run(action.run_id)
        profile = self._profile(run, attempt.spec.profile_id)
        stage = next(
            (item for item in run.spec.workflow.stages if item.id == attempt.stage_id), None
        )
        if stage is None:
            raise LedgerInvariantError(f"attempt references missing stage {attempt.stage_id}")
        outputs = tuple(dict.fromkeys((*profile.required_outputs, *stage.required_outputs)))
        if (
            self._requires_backend_preflight_record()
            and not attempt.state.worker_lifecycle_owner_id
        ):
            raise LedgerInvariantError(
                "Codex launch is missing its committed preparation owner intent"
            )
        return PreflightContext(
            preparation_id=str(action.action_id),
            record_id=str(uuid5(NAMESPACE_URL, f"backend-preflight:{action.action_id}")),
            project_path=run.project_config.path,
            required_outputs=outputs,
            binding_id=profile.model_binding,
            lifecycle_owner_id=attempt.state.worker_lifecycle_owner_id,
        )

    def _ensure_backend_preparation_intent(
        self, action: OutboxAction, attempt: PersistedAttempt
    ) -> PersistedAttempt:
        """Durably bind legacy pending launches before any backend preflight side effect."""
        preparation_id = str(action.action_id)
        owner_id = derive_lifecycle_owner_id(preparation_id)
        if attempt.state.worker_lifecycle_owner_id == owner_id:
            return attempt
        if attempt.state.worker_lifecycle_owner_id is not None:
            raise LedgerInvariantError("attempt has a conflicting lifecycle owner intent")
        event = BackendPreparationIntentRecordedEvent(
            event_id=uuid4(),
            run_id=action.run_id,
            occurred_at=self._now(),
            actor=self.actor,
            kind=EventKind.BACKEND_PREPARATION_INTENT_RECORDED,
            action_id=action.action_id,
            attempt_id=attempt.spec.attempt_id,
            preparation_id=preparation_id,
            lifecycle_owner_id=owner_id,
            attempt_spec_hash=content_hash(canonical_json(attempt.spec)),
        )

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            if current.spec != attempt.spec:
                raise LedgerInvariantError("attempt specification changed before preparation")
            if current.state.worker_lifecycle_owner_id not in {None, owner_id}:
                raise LedgerInvariantError("attempt has a conflicting lifecycle owner intent")
            updated = current.state.model_copy(update={"worker_lifecycle_owner_id": owner_id})
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=event.occurred_at,
                attempt_updates=(updated,),
                events=(event,),
            )

        self._commit(action.run_id, build)
        return self.ledger.get_attempt(attempt.spec.attempt_id)

    def _persist_backend_preflight(
        self,
        action: OutboxAction,
        attempt: PersistedAttempt,
        context: PreflightContext,
        accepted: bool,
        snapshot: BackendPreflightSnapshot,
        prepared_handle: WorkerHandle | None = None,
    ) -> BackendPreflightRecord:
        occurred_at = self._now()
        record = BackendPreflightRecord(
            record_id=context.record_id,
            run_id=action.run_id,
            attempt_id=attempt.spec.attempt_id,
            preparation_id=context.preparation_id,
            attempt_spec_hash=content_hash(canonical_json(attempt.spec)),
            accepted=accepted,
            occurred_at=occurred_at,
            snapshot=snapshot,
            record_hash="0" * 64,
        )
        record_hash = content_hash(
            canonical_json(record.model_dump(mode="json", exclude={"record_hash"}))
        )
        record = record.model_copy(update={"record_hash": record_hash})
        event = BackendPreflightRecordedEvent(
            event_id=uuid4(),
            run_id=action.run_id,
            occurred_at=occurred_at,
            actor=self.actor,
            kind=EventKind.BACKEND_PREFLIGHT_RECORDED,
            record_id=record.record_id,
            attempt_id=record.attempt_id,
            preparation_id=record.preparation_id,
            record_hash=record.record_hash,
            accepted=record.accepted,
        )

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            if current.spec != attempt.spec:
                raise LedgerInvariantError("attempt specification changed after preflight")
            if current.state.worker_lifecycle_owner_id not in {
                None,
                context.lifecycle_owner_id,
            }:
                raise LedgerInvariantError("preflight owner differs from its durable owner intent")
            if prepared_handle is not None and current.state.worker_lifecycle_owner_id not in {
                None,
                prepared_handle.lifecycle_owner_id,
            }:
                raise LedgerInvariantError("prepared owner differs from its durable owner intent")
            if current.state.backend_preflight_record_id not in {None, record.record_id}:
                raise LedgerInvariantError("attempt already has a different preflight record")
            updated = current.state.model_copy(
                update={
                    "backend_preflight_record_id": record.record_id,
                    "backend_preflight_record_hash": record.record_hash,
                    **(
                        {
                            "worker_handle_id": prepared_handle.handle_id,
                            "worker_backend_version": prepared_handle.backend_version,
                            "worker_session_id": prepared_handle.session_id,
                            "worker_thread_id": prepared_handle.thread_id,
                            "worker_turn_id": None,
                            "worker_lifecycle_owner_id": prepared_handle.lifecycle_owner_id,
                        }
                        if prepared_handle is not None
                        else {}
                    ),
                }
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=occurred_at,
                attempt_updates=(updated,),
                backend_preflight_records=(record,),
                events=(event,),
            )

        self._commit(action.run_id, build)
        return record

    @staticmethod
    def _inhibits_launches(status: RunStatus) -> bool:
        return status in {
            RunStatus.PAUSE_REQUESTED,
            RunStatus.PAUSED,
            RunStatus.STOPPING,
            RunStatus.STOPPED,
            RunStatus.ATTENTION_REQUIRED,
            RunStatus.FAILED,
            RunStatus.SUCCEEDED,
        }

    def _cancel_unlaunched_action(
        self, action: OutboxAction, attempt: PersistedAttempt, reason: str
    ) -> None:
        releases = self._reservation_releases(action.run_id, attempt.spec.attempt_id)

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            if current.state.status not in {AttemptStatus.LAUNCHING, AttemptStatus.PENDING}:
                return LedgerMutation(
                    command_id=uuid4(),
                    run_id=run.run_id,
                    expected_revision=run.state.revision,
                    actor=self.actor,
                    occurred_at=self._now(),
                )
            cancelled = current.state.model_copy(
                update={
                    "status": AttemptStatus.CANCELLED,
                    "finished_at": self._now(),
                    "error_class": FailureClass.CANCELLED,
                    "error_summary": reason,
                    "safe_to_retry": True,
                }
            )
            next_status = self._status_after_settlement(run, attempt.spec.attempt_id)
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=next_status,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=None,
                    resume_status=None,
                ),
                attempt_updates=(cancelled,),
                outbox_outcomes=(
                    OutboxOutcomeChange(
                        action_id=action.action_id,
                        status=OutboxStatus.REJECTED,
                        result=reason,
                    ),
                ),
                reservations=releases,
            )

        self._commit(action.run_id, build)

    async def run_until_stalled(self, run_id: str, *, max_steps: int = 10_000) -> RunStatus:
        """Drive internal transitions and fake workers until completion or a genuine stall."""
        await self.recover(run_id)
        for _ in range(max_steps):
            await self._process_ready_decisions(run_id)
            changed = self.advance(run_id)
            dispatched = await self.dispatch_pending(run_id)
            if self.ledger.get_run(run_id).state.status in _TERMINAL_RUN_STATES:
                await self._join_finished_workers()
                return self.ledger.get_run(run_id).state.status
            if dispatched:
                continue
            active = tuple(self._workers.values())
            if active:
                done, _pending = await asyncio.wait(active, return_when=asyncio.FIRST_COMPLETED)
                for task in done:
                    task.result()
                continue
            if changed:
                continue
            return self.ledger.get_run(run_id).state.status
        raise RuntimeError("run exceeded its deterministic execution-step bound")

    async def _process_ready_decisions(self, run_id: str) -> bool:
        run = self.ledger.get_run(run_id)
        questions = run.spec.workflow.policy.decision_questions
        if not questions:
            return False
        records = self.ledger.list_decision_records(run_id)
        for question in questions:
            prior = next(
                (item for item in reversed(records) if item.question_id == question.question_id),
                None,
            )
            if prior is not None:
                if prior.completed_at is None:
                    failure = DecisionEngineFailure(
                        decision_id=prior.decision_id,
                        classification=DecisionFailureClass.ENGINE_UNAVAILABLE,
                        detail="coordinator restarted before this decision reached a disposition",
                    )
                    await self._finalize_decision(run_id, prior, failure)
                    return True
                continue

            # An explicit run-level profile selection is already coordinator input.
            if any(
                item.path == f"stage.{question.stage_id}.profile"
                for item in run.spec.applied_overrides
            ):
                continue
            # Preserve an explicit human redirect recorded through the control path.
            if self.ledger.get_stage_redirect(run_id, question.stage_id) is not None:
                continue
            if run.state.status not in {RunStatus.READY, RunStatus.RUNNING}:
                continue
            stage = next(
                (item for item in run.spec.workflow.stages if item.id == question.stage_id), None
            )
            projection = next(
                (item for item in run.stages if item.stage_id == question.stage_id), None
            )
            if (
                stage is None
                or projection is None
                or projection.status
                not in {
                    StageStatus.PENDING,
                    StageStatus.READY,
                }
            ):
                continue
            stage_by_id = {item.stage_id: item for item in run.stages}
            if any(
                stage_by_id[dependency].status not in _SUCCESSFUL_STAGE_STATES
                for dependency in stage.depends_on
            ):
                continue
            repair_gate = stage_by_id.get("repair_gate")
            repair_decision = (
                repair_gate.result.decision
                if repair_gate is not None and repair_gate.result is not None
                else None
            )
            if evaluate_condition(stage, repair_decision) is not True:
                continue
            await self._request_and_run_decision(run, question)
            return True
        return False

    async def _request_and_run_decision(
        self, run: PersistedRun, question: ResolvedDecisionQuestion
    ) -> None:
        options = tuple(
            DecisionOption(
                outcome_id=profile_id,
                label=self._profile(run, profile_id).name,
            )
            for profile_id in self._decision_outcome_ids(run, question.stage_id)
        )
        evidence: list[DecisionEvidence] = []
        missing: list[str] = []
        requirements = question.evidence_requirements
        for order, requirement in enumerate(requirements):
            if requirement.kind == "run_task":
                if len(run.spec.task.encode("utf-8")) > 16_384:
                    missing.append(requirement.source_ref)
                    continue
                evidence.append(
                    DecisionEvidence(
                        source_ref="run.task",
                        source_revision=run.spec.snapshot_hash,
                        content_hash=content_hash(run.spec.task),
                        inclusion_reason=requirement.inclusion_reason,
                        order=order,
                        current_run_revision=run.state.revision,
                        value=run.spec.task,
                    )
                )
                continue
            projection = next(
                (item for item in run.stages if item.stage_id == requirement.stage_id), None
            )
            artifact = (
                next(
                    (
                        item
                        for item in projection.result.outputs
                        if item.name == requirement.output_name
                    ),
                    None,
                )
                if projection is not None and projection.result is not None
                else None
            )
            if projection is None or projection.status != StageStatus.SUCCEEDED or artifact is None:
                missing.append(requirement.source_ref)
                continue
            evidence.append(
                DecisionEvidence(
                    source_ref=requirement.source_ref,
                    source_revision=artifact.content_hash,
                    content_hash=artifact.content_hash,
                    inclusion_reason=requirement.inclusion_reason,
                    order=order,
                    current_run_revision=run.state.revision,
                )
            )

        now = self._now()
        request = DecisionRequest(
            decision_id=uuid4(),
            run_id=run.run_id,
            current_run_revision=run.state.revision,
            question_id=question.question_id,
            question_revision=question.revision,
            question=question.question,
            allowed_outcomes=options,
            required_evidence_refs=tuple(item.source_ref for item in requirements),
            missing_evidence_refs=tuple(missing),
            evidence=tuple(evidence),
            inference_binding=question.inference_binding,
            acceptance_policy=question.acceptance_policy,
            created_at=now,
        )
        request_hash = decision_request_hash(request)
        record = DecisionRecord(
            request=request,
            request_hash=request_hash,
            request_persisted_revision=run.state.revision + 1,
            created_at=now,
        )
        engine = self.decision_engine
        if (
            engine is None
            and request.inference_binding.mechanism == DecisionMechanism.DETERMINISTIC_POLICY
        ):
            from orchestrator.backends.decision import DeterministicDecisionEngine

            engine = DeterministicDecisionEngine()
        can_invoke = not missing and engine is not None
        request_events: list[Event] = [
            self._decision_event(
                request,
                EventKind.DECISION_REQUESTED,
                request_hash=request_hash,
            )
        ]
        if can_invoke:
            request_events.append(
                self._decision_event(
                    request,
                    EventKind.DECISION_INFERENCE_STARTED,
                    request_hash=request_hash,
                )
            )
        receipt = self.ledger.apply(
            LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=now,
                run_update=RunProjectionUpdate(elapsed_seconds=self._elapsed(run)),
                decision_records=(record,),
                events=tuple(request_events),
            )
        )
        if receipt.outcome != CommandOutcome.ACCEPTED:
            return

        if missing:
            reply: DecisionEngineReply = DecisionEngineFailure(
                decision_id=request.decision_id,
                classification=DecisionFailureClass.MISSING_EVIDENCE,
                detail="required decision evidence is missing: " + ", ".join(missing),
            )
        elif engine is None:
            reply = DecisionEngineFailure(
                decision_id=request.decision_id,
                classification=DecisionFailureClass.ENGINE_UNAVAILABLE,
                detail="no engine is configured for the resolved inference mechanism",
            )
        else:
            try:
                raw_reply = await asyncio.wait_for(
                    engine.decide(request), timeout=self.decision_timeout_seconds
                )
                if isinstance(raw_reply, DecisionResult):
                    reply = DecisionResult.model_validate(raw_reply.model_dump(mode="python"))
                elif isinstance(raw_reply, DecisionEngineFailure):
                    reply = DecisionEngineFailure.model_validate(
                        raw_reply.model_dump(mode="python")
                    )
                else:
                    reply = DecisionEngineFailure(
                        decision_id=request.decision_id,
                        classification=DecisionFailureClass.MALFORMED_RESULT,
                        detail="decision engine returned a value outside the normalized contract",
                    )
            except TimeoutError:
                reply = DecisionEngineFailure(
                    decision_id=request.decision_id,
                    classification=DecisionFailureClass.ENGINE_TIMEOUT,
                    detail=f"decision inference exceeded {self.decision_timeout_seconds:g} seconds",
                )
            except ValidationError:
                reply = DecisionEngineFailure(
                    decision_id=request.decision_id,
                    classification=DecisionFailureClass.MALFORMED_RESULT,
                    detail="decision engine response failed normalized contract validation",
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                reply = DecisionEngineFailure(
                    decision_id=request.decision_id,
                    classification=DecisionFailureClass.ENGINE_ERROR,
                    detail=f"decision engine raised {type(error).__name__}",
                )
        await self._finalize_decision(run.run_id, record, reply)

    async def _finalize_decision(
        self,
        run_id: str,
        record: DecisionRecord,
        reply: DecisionEngineReply,
    ) -> None:
        request = record.request
        question = next(
            item
            for item in self.ledger.get_run(run_id).spec.workflow.policy.decision_questions
            if item.question_id == request.question_id
        )
        if reply.decision_id != request.decision_id:
            reply = DecisionEngineFailure(
                decision_id=request.decision_id,
                classification=DecisionFailureClass.INCOMPATIBLE_RESULT,
                detail=f"engine reply belongs to another decision: {reply.decision_id}",
            )
        for _ in range(5):
            current = self.ledger.get_run(run_id)
            current_allowed = self._decision_outcome_ids(current, question.stage_id)
            evaluation_revision = (
                request.current_run_revision
                if current.state.revision == record.request_persisted_revision
                else current.state.revision
            )
            disposition = evaluate_decision(
                request,
                reply,
                current_run_revision=evaluation_revision,
                currently_allowed_outcomes=set(current_allowed),
                evaluated_at=self._now(),
            )
            if disposition.policy_action in {
                DecisionPolicyAction.CONTINUE,
                DecisionPolicyAction.FALLBACK,
            }:
                if disposition.selected_outcome_id not in current_allowed:
                    disposition = disposition.model_copy(
                        update={
                            "status": DecisionDispositionStatus.REJECTED,
                            "policy_action": DecisionPolicyAction.ATTENTION_REQUIRED,
                            "reason": DecisionDispositionReason.OUTCOME_NO_LONGER_ALLOWED,
                            "selected_outcome_id": None,
                        }
                    )
            resulting_revision = current.state.revision + 1
            disposition = disposition.model_copy(
                update={
                    "resulting_run_revision": resulting_revision,
                    "action_reference": str(request.decision_id),
                }
            )
            completed = record.model_copy(
                update={
                    "result": reply if isinstance(reply, DecisionResult) else None,
                    "failure": reply if isinstance(reply, DecisionEngineFailure) else None,
                    "disposition": disposition,
                    "completed_at": self._now(),
                }
            )
            events = self._decision_completion_events(request, reply, disposition)
            run_update = RunProjectionUpdate(elapsed_seconds=self._elapsed(current))
            stage_redirects: tuple[StageRedirect, ...] = ()
            if disposition.status in {
                DecisionDispositionStatus.ACCEPTED,
                DecisionDispositionStatus.FALLBACK,
            }:
                selected = disposition.selected_outcome_id
                if selected is None:
                    raise LedgerInvariantError("accepted decision omitted its selected outcome")
                run_update = RunProjectionUpdate(
                    elapsed_seconds=self._elapsed(current),
                )
                stage_redirects = (
                    StageRedirect(
                        run_id=run_id,
                        stage_id=question.stage_id,
                        recipient_profile_id=selected,
                        command_id=request.decision_id,
                        updated_at=self._now(),
                    ),
                )
            elif current.state.status not in {
                RunStatus.PAUSE_REQUESTED,
                RunStatus.PAUSED,
                RunStatus.STOPPING,
                RunStatus.STOPPED,
                RunStatus.SUCCEEDED,
                RunStatus.FAILED,
                RunStatus.ATTENTION_REQUIRED,
            }:
                reason = (
                    f"decision {request.question_id} requires attention: {disposition.reason.value}"
                )
                run_update = RunProjectionUpdate(
                    status=RunStatus.ATTENTION_REQUIRED,
                    elapsed_seconds=self._elapsed(current),
                    attention_reason=reason,
                    resume_status=current.state.resume_status or current.state.status,
                )
                events = (
                    *events,
                    RunStatusChangedEvent(
                        event_id=uuid4(),
                        run_id=run_id,
                        occurred_at=self._now(),
                        actor=self.actor,
                        kind=EventKind.RUN_STATUS_CHANGED,
                        previous=current.state.status,
                        current=RunStatus.ATTENTION_REQUIRED,
                        reason=reason,
                        cause_event_id=events[-1].event_id if events else None,
                    ),
                )
            receipt = self.ledger.apply(
                LedgerMutation(
                    command_id=uuid4(),
                    run_id=run_id,
                    expected_revision=current.state.revision,
                    actor=self.actor,
                    occurred_at=self._now(),
                    run_update=run_update,
                    decision_records=(completed,),
                    stage_redirects=stage_redirects,
                    events=events,
                )
            )
            if receipt.outcome == CommandOutcome.ACCEPTED:
                return
            if not receipt.reason or not receipt.reason.startswith("stale_revision"):
                raise LedgerInvariantError(receipt.reason or "decision disposition was rejected")
        raise LedgerInvariantError("run kept changing while persisting a decision disposition")

    def _decision_outcome_ids(self, run: PersistedRun, stage_id: str) -> tuple[str, ...]:
        redirect = next(
            (item for item in run.spec.workflow.allowed_redirects if item.stage == stage_id), None
        )
        if redirect is None:
            raise LedgerInvariantError(
                f"decision stage {stage_id} has no frozen redirect allowlist"
            )
        allowed_profiles = set(run.spec.workflow.allowed_profiles)
        stage = next((item for item in run.spec.workflow.stages if item.id == stage_id), None)
        if stage is None:
            raise LedgerInvariantError(
                f"decision stage {stage_id} is absent from the frozen workflow"
            )
        profile_ids = {item.id for item in run.spec.profiles}
        return tuple(
            profile_id
            for profile_id in redirect.allowed_profiles
            if profile_id in stage.allowed_profiles
            and profile_id in allowed_profiles
            and profile_id in profile_ids
        )

    def _decision_event(
        self,
        request: DecisionRequest,
        kind: DecisionEventKind,
        *,
        request_hash: str,
        result_hash: str | None = None,
        disposition: DecisionDisposition | None = None,
        detail: str | None = None,
    ) -> DecisionLifecycleEvent:
        return DecisionLifecycleEvent(
            event_id=uuid4(),
            run_id=request.run_id,
            occurred_at=self._now(),
            actor=self.actor,
            kind=kind,
            decision_id=request.decision_id,
            question_id=request.question_id,
            request_hash=request_hash,
            result_hash=result_hash,
            disposition_status=(disposition.status.value if disposition else None),
            disposition_reason=(disposition.reason.value if disposition else None),
            outcome_id=(disposition.selected_outcome_id if disposition else None),
            detail=detail,
        )

    def _decision_completion_events(
        self,
        request: DecisionRequest,
        reply: DecisionEngineReply,
        disposition: DecisionDisposition,
    ) -> tuple[Event, ...]:
        request_hash = decision_request_hash(request)
        result_hash = decision_result_hash(reply) if isinstance(reply, DecisionResult) else None
        events: list[Event] = []
        if isinstance(reply, DecisionEngineFailure):
            events.append(
                self._decision_event(
                    request,
                    EventKind.DECISION_INFERENCE_FAILED,
                    request_hash=request_hash,
                    detail=f"{reply.classification.value}: {reply.detail}",
                )
            )
        else:
            events.append(
                self._decision_event(
                    request,
                    EventKind.DECISION_RESULT_RECORDED,
                    request_hash=request_hash,
                    result_hash=result_hash,
                )
            )
        events.append(
            self._decision_event(
                request,
                EventKind.DECISION_POLICY_EVALUATED,
                request_hash=request_hash,
                result_hash=result_hash,
                disposition=disposition,
            )
        )
        reason = disposition.reason
        kind: DecisionEventKind
        if disposition.status == DecisionDispositionStatus.ABSTAINED:
            kind = EventKind.DECISION_ABSTAINED
        elif reason in {
            DecisionDispositionReason.STALE_RUN_REVISION,
            DecisionDispositionReason.STALE_EVIDENCE,
        }:
            kind = EventKind.DECISION_RESULT_STALE
        elif reason in {
            DecisionDispositionReason.DISALLOWED_OUTCOME,
            DecisionDispositionReason.OUTCOME_NO_LONGER_ALLOWED,
        }:
            kind = EventKind.DECISION_RESULT_DISALLOWED
        elif disposition.status == DecisionDispositionStatus.REJECTED or (
            isinstance(reply, DecisionResult)
            and reply.result_class
            in {DecisionResultClass.MALFORMED, DecisionResultClass.INCOMPATIBLE}
        ):
            kind = EventKind.DECISION_RESULT_REJECTED
        elif disposition.status == DecisionDispositionStatus.ACCEPTED:
            kind = EventKind.DECISION_ACCEPTED
        elif disposition.status == DecisionDispositionStatus.FALLBACK:
            kind = EventKind.DECISION_FALLBACK
        else:
            kind = EventKind.DECISION_ATTENTION_REQUIRED
        events.append(
            self._decision_event(
                request,
                kind,
                request_hash=request_hash,
                result_hash=result_hash,
                disposition=disposition,
            )
        )
        return tuple(events)

    async def wait_for_workers(self) -> None:
        """Wait for every worker event stream currently owned by this coordinator."""
        tasks = tuple(self._workers.values())
        if tasks:
            await asyncio.gather(*tasks)

    async def recover(self, run_id: str) -> int:
        """Reconcile ambiguous persisted launches and controls without replaying them."""
        self.ledger.get_run(run_id)
        reconciled = 0
        for action in self.ledger.list_outbox_actions(run_id):
            if action.status != OutboxStatus.CLAIMED or action.kind == "launch_attempt":
                continue
            attempt_id = str(action.payload.get("attempt_id", ""))
            try:
                attempt = self.ledger.get_attempt(attempt_id)
            except KeyError:
                self._record_orphan_control_unknown(
                    action, "claimed control references a missing attempt after restart"
                )
                continue
            is_interrupt = action.kind == "interrupt_attempt"
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                "control delivery was claimed before restart; acknowledgement is unknown",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=is_interrupt,
                mark_input_uncertain=action.kind == "steer_attempt",
                attention_reason="control delivery outcome is unresolved after restart",
            )

        self.mark_claimed_launches_unknown(run_id)
        for attempt in self.ledger.list_attempts(run_id):
            worker = self._workers.get(attempt.spec.attempt_id)
            if worker is not None and not worker.done():
                continue
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            if current.state.status not in _ACTIVE_ATTEMPT_STATES | {AttemptStatus.OUTCOME_UNKNOWN}:
                continue
            if current.state.status == AttemptStatus.LAUNCHING and self._has_unclaimed_launch(
                run_id, current.spec.attempt_id
            ):
                continue
            if current.state.status != AttemptStatus.OUTCOME_UNKNOWN:
                self._mark_unknown_launch(
                    self._action_for_attempt(current.spec.attempt_id),
                    current,
                    "reconciliation pending: active attempt has no local worker owner",
                )
            await self._inspect_attempt(current.spec.attempt_id, uuid4())
            reconciled += 1
        return reconciled

    async def _inspect_attempt(self, attempt_id: str, reconciliation_id: UUID) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        run = self.ledger.get_run(attempt.spec.run_id)
        requested = InterventionLifecycleEvent(
            event_id=uuid4(),
            run_id=run.run_id,
            occurred_at=self._now(),
            actor=self.actor,
            kind=EventKind.RECONCILIATION_REQUESTED,
            command_id=reconciliation_id,
            attempt_id=attempt_id,
            detail="backend inspection requested for persisted worker identity",
            resulting_run_revision=run.state.revision + 1,
        )
        self._commit(
            run.run_id,
            lambda current: LedgerMutation(
                command_id=uuid4(),
                run_id=current.run_id,
                expected_revision=current.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                events=(requested,),
            ),
        )

        latest = self.ledger.get_attempt(attempt_id)
        if latest.state.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            current_run = self.ledger.get_run(run.run_id)
            restored_status = self._status_after_reconciliation(
                current_run, attempt_id, latest.state.status
            )
            resolved = InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=run.run_id,
                occurred_at=self._now(),
                actor=self.actor,
                kind=EventKind.RECONCILIATION_RESOLVED,
                command_id=reconciliation_id,
                attempt_id=attempt_id,
                detail="persisted terminal attempt evidence resolved worker ownership",
                reconciled_status=latest.state.status,
                reconciliation_known=True,
            )

            def resolve_persisted_terminal(current: PersistedRun) -> LedgerMutation:
                events: list[Event] = [resolved]
                if restored_status != current.state.status:
                    events.append(
                        RunStatusChangedEvent(
                            event_id=uuid4(),
                            run_id=current.run_id,
                            occurred_at=self._now(),
                            actor=self.actor,
                            kind=EventKind.RUN_STATUS_CHANGED,
                            previous=current.state.status,
                            current=restored_status,
                            reason="persisted terminal evidence resolved the control race",
                            cause_event_id=resolved.event_id,
                        )
                    )
                return LedgerMutation(
                    command_id=uuid4(),
                    run_id=current.run_id,
                    expected_revision=current.state.revision,
                    actor=self.actor,
                    occurred_at=self._now(),
                    run_update=(
                        RunProjectionUpdate(
                            status=restored_status,
                            elapsed_seconds=self._elapsed(current),
                            attention_reason=(
                                current.state.attention_reason
                                if restored_status == RunStatus.ATTENTION_REQUIRED
                                else None
                            ),
                            resume_status=(
                                current.state.resume_status
                                if restored_status == RunStatus.ATTENTION_REQUIRED
                                else None
                            ),
                        )
                        if restored_status != current.state.status
                        else None
                    ),
                    events=tuple(events),
                )

            self._commit(run.run_id, resolve_persisted_terminal)
            return

        state = self.ledger.get_attempt(attempt_id).state
        identity = WorkerIdentity(
            backend=attempt.spec.backend,
            backend_version=state.worker_backend_version,
            attempt_id=attempt_id,
            session_id=state.worker_session_id,
            thread_id=state.worker_thread_id,
            turn_id=state.worker_turn_id,
            lifecycle_owner_id=state.worker_lifecycle_owner_id,
        )
        if not state.worker_lifecycle_owner_id or (
            not state.worker_handle_id and not self._requires_backend_preflight_record()
        ):
            reconciliation = Reconciliation(
                known=False,
                detail="persisted worker identity is incomplete; inspection was not attempted",
            )
        else:
            try:
                completed, raw = await self._bounded_call(self.backend.inspect(identity))
                reconciliation = (
                    raw
                    if completed and isinstance(raw, Reconciliation)
                    else Reconciliation(known=False, detail="backend inspection timed out")
                )
            except asyncio.CancelledError:
                raise
            except BaseException as error:
                reconciliation = Reconciliation(
                    known=False,
                    detail=f"backend inspection failed: {type(error).__name__}",
                )

        now = self._now()
        if (
            reconciliation.known
            and reconciliation.status == AttemptStatus.SUCCEEDED
            and reconciliation.terminal_result is not None
        ):
            event = InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=run.run_id,
                occurred_at=now,
                actor=self.actor,
                kind=EventKind.RECONCILIATION_RESOLVED,
                command_id=reconciliation_id,
                attempt_id=attempt_id,
                detail=reconciliation.detail or "worker terminal result was reconciled",
                reconciled_status=reconciliation.status,
                reconciliation_known=True,
            )
            terminal = WorkerTerminalEvent(
                attempt_id=attempt_id,
                sequence=1,
                occurred_at=now,
                kind=WorkerEventKind.TERMINAL,
                result=reconciliation.terminal_result,
            )
            self._settle_terminal(
                attempt_id,
                terminal,
                reconciliation_event=event,
                reconciliation=reconciliation,
            )
            return

        if reconciliation.known and reconciliation.status in {
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            event = InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=run.run_id,
                occurred_at=now,
                actor=self.actor,
                kind=EventKind.RECONCILIATION_RESOLVED,
                command_id=reconciliation_id,
                attempt_id=attempt_id,
                detail=reconciliation.detail or "worker terminal status was reconciled",
                reconciled_status=reconciliation.status,
                reconciliation_known=True,
            )
            failure_class = (
                reconciliation.failure_class
                or {
                    AttemptStatus.TIMED_OUT: FailureClass.TIMEOUT,
                    AttemptStatus.CANCELLED: FailureClass.CANCELLED,
                    AttemptStatus.FAILED: FailureClass.WORKER_FAILURE,
                }[reconciliation.status]
            )
            self._settle_failure(
                attempt_id,
                reconciliation.status,
                failure_class,
                reconciliation.detail or "worker terminal status was reconciled",
                safe_to_retry=reconciliation.safe_to_retry,
                reconciliation_event=event,
            )
            return

        detail = reconciliation.detail or (
            f"backend reports nonterminal status {reconciliation.status.value}"
            if reconciliation.status is not None
            else "backend cannot establish worker outcome"
        )
        unresolved = InterventionLifecycleEvent(
            event_id=uuid4(),
            run_id=run.run_id,
            occurred_at=now,
            actor=self.actor,
            kind=EventKind.RECONCILIATION_UNRESOLVED,
            command_id=reconciliation_id,
            attempt_id=attempt_id,
            detail=detail,
            reconciled_status=reconciliation.status,
            reconciliation_known=reconciliation.known,
        )

        def persist_unresolved(current_run: PersistedRun) -> LedgerMutation:
            current_attempt = self.ledger.get_attempt(attempt_id)
            reason = f"reconciliation pending: {detail}"
            worker = self._workers.get(attempt_id)
            persisted_status = (
                current_attempt.state.status
                if worker is not None and not worker.done()
                else AttemptStatus.OUTCOME_UNKNOWN
            )
            update = current_attempt.state.model_copy(
                update={"status": persisted_status, "error_summary": reason}
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=current_run.run_id,
                expected_revision=current_run.state.revision,
                actor=self.actor,
                occurred_at=now,
                run_update=RunProjectionUpdate(
                    status=RunStatus.ATTENTION_REQUIRED,
                    elapsed_seconds=self._elapsed(current_run),
                    attention_reason=reason,
                    resume_status=current_run.state.resume_status or current_run.state.status,
                ),
                attempt_updates=(update,),
                events=(unresolved,),
            )

        self._commit(run.run_id, persist_unresolved)

    async def apply_intervention(self, request: Intervention) -> CommandReceipt:
        """Validate, persist and execute one exact, revision-checked control command."""
        if request.run_id is None:
            raise ValueError("intervention must name its run_id")
        run = self.ledger.get_run(request.run_id)
        try:
            scope, target_id = self._intervention_target(request)
        except ValueError as error:
            scope, target_id = self._nominal_intervention_target(request)
            normalized = request.model_copy(update={"run_id": run.run_id, "target_scope": scope})
            return self._record_rejected_intervention(normalized, run, scope, target_id, str(error))
        normalized = request.model_copy(update={"run_id": run.run_id, "target_scope": scope})
        prior_record = next(
            (
                item
                for item in self.ledger.list_intervention_records(run.run_id)
                if item.command_id == request.command_id
            ),
            None,
        )
        prior_receipt = self.ledger.get_command_receipt(request.command_id)
        if prior_receipt is not None:
            if prior_record is not None and prior_record.payload != normalized.model_dump(
                mode="json"
            ):
                raise CommandIdConflict(
                    f"intervention ID {request.command_id} was reused for another request"
                )
            return prior_receipt

        if request.expected_run_revision != run.state.revision:
            return self._record_rejected_intervention(
                normalized,
                run,
                scope,
                target_id,
                f"stale_revision: expected {request.expected_run_revision}, "
                f"current {run.state.revision}",
            )

        try:
            self._validate_intervention(normalized, run)
        except ValueError as error:
            return self._record_rejected_intervention(normalized, run, scope, target_id, str(error))

        if isinstance(normalized, ResumeIntervention):
            await self.recover(run.run_id)
            run = self.ledger.get_run(run.run_id)
            if run.state.status != RunStatus.PAUSED:
                return self._record_rejected_intervention(
                    normalized,
                    run,
                    scope,
                    target_id,
                    "resume requires a paused run with reconciled ownership",
                    expected_revision=run.state.revision,
                )

        now = self._now()
        request_event_id = uuid4()
        events: list[Event] = [
            InterventionRequestedEvent(
                event_id=request_event_id,
                run_id=run.run_id,
                occurred_at=now,
                actor=normalized.actor,
                kind=EventKind.INTERVENTION_REQUESTED,
                intervention=normalized,
            ),
            InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=run.run_id,
                occurred_at=now,
                actor=normalized.actor,
                kind=EventKind.INTERVENTION_VALIDATED,
                command_id=normalized.command_id,
                detail="validated against current run state and resolved policy",
            ),
        ]
        active_attempts = self.ledger.list_attempts(run.run_id)
        run_status = run.state.status
        reason: str | None = None
        attempt_updates: list[AttemptState] = []
        outbox_actions: list[OutboxIntent] = []
        deliveries: list[ControlDelivery] = []
        stage_redirects: list[StageRedirect] = []
        timeout_event: Event | None = None

        if isinstance(normalized, PauseIntervention):
            run_status = (
                RunStatus.PAUSE_REQUESTED
                if any(item.state.status in _ACTIVE_ATTEMPT_STATES for item in active_attempts)
                else RunStatus.PAUSED
            )
            reason = "pause requested; active attempts will drain"
        elif isinstance(normalized, ResumeIntervention):
            run_status = RunStatus.RUNNING
            reason = "run resumed after reconciliation"
        elif isinstance(normalized, StopIntervention):
            targets = [
                item for item in active_attempts if item.state.status in _ACTIVE_ATTEMPT_STATES
            ]
            run_status = RunStatus.STOPPING if targets else RunStatus.STOPPED
            reason = "workflow stop requested"
            for attempt in targets:
                if attempt.state.status == AttemptStatus.RUNNING and self._worker_handle(attempt):
                    self._add_interrupt_intent(
                        normalized, attempt, now, outbox_actions, deliveries, attempt_updates
                    )
                elif self._has_unclaimed_launch(run.run_id, attempt.spec.attempt_id):
                    continue
                else:
                    attempt_updates.append(
                        attempt.state.model_copy(
                            update={
                                "status": AttemptStatus.OUTCOME_UNKNOWN,
                                "error_summary": (
                                    "stop requested while launch ownership was ambiguous"
                                ),
                                "safe_to_retry": False,
                            }
                        )
                    )
                    run_status = RunStatus.ATTENTION_REQUIRED
                    reason = "stop requested but worker launch ownership is unresolved"
        elif isinstance(normalized, StopAttemptIntervention):
            target = self.ledger.get_attempt(normalized.attempt_id)
            self._add_interrupt_intent(
                normalized, target, now, outbox_actions, deliveries, attempt_updates
            )
            run_status = RunStatus.ATTENTION_REQUIRED
            reason = "selected attempt stop requested; its required slot needs retry or run stop"
            if normalized.reason == "timeout":
                reason = "attempt timeout detected; bounded shutdown is in progress"
                timeout_event = TimeoutDetectedEvent(
                    event_id=uuid4(),
                    run_id=run.run_id,
                    occurred_at=now,
                    actor=self.actor,
                    kind=EventKind.TIMEOUT_DETECTED,
                    attempt_id=normalized.attempt_id,
                    timeout_seconds=self._profile(run, target.spec.profile_id).timeout_seconds,
                )
        elif isinstance(normalized, SteerIntervention):
            target = self.ledger.get_attempt(normalized.attempt_id)
            new_revision = self._steered_input_revision(target, normalized)
            handle = self._worker_handle(target)
            assert handle is not None
            delivery = ControlDelivery(
                action_id=uuid4(),
                attempt_id=target.spec.attempt_id,
                status=ControlDeliveryStatus.PENDING,
                requested_at=now,
                effective_input_revision=new_revision,
                worker_handle_id=handle.handle_id,
                worker_thread_id=handle.thread_id,
                worker_turn_id=handle.turn_id,
            )
            deliveries.append(delivery)
            outbox_actions.append(
                OutboxIntent(
                    action_id=delivery.action_id,
                    action_key=f"control:{normalized.command_id}:{target.spec.attempt_id}:steer",
                    kind="steer_attempt",
                    payload={
                        "command_id": str(normalized.command_id),
                        "attempt_id": target.spec.attempt_id,
                        "expected_turn_id": normalized.expected_turn_id,
                        "instruction": normalized.instruction,
                        "effective_input_revision": new_revision,
                    },
                )
            )
        elif isinstance(normalized, RetryIntervention):
            target = self.ledger.get_attempt(normalized.attempt_id)
            attempt_updates.append(target.state.model_copy(update={"retry_authorized": True}))
            run_status = run.state.resume_status or RunStatus.RUNNING
            reason = "explicit retry authorized"
        elif isinstance(normalized, RedirectIntervention):
            stage_redirects.append(
                StageRedirect(
                    run_id=run.run_id,
                    stage_id=normalized.stage_id,
                    recipient_profile_id=normalized.recipient_profile_id,
                    command_id=normalized.command_id,
                    updated_at=now,
                )
            )

        if timeout_event is not None:
            events.append(timeout_event)
        if run_status != run.state.status:
            events.append(
                InterventionLifecycleEvent(
                    event_id=uuid4(),
                    run_id=run.run_id,
                    occurred_at=now,
                    actor=normalized.actor,
                    kind=EventKind.INTERVENTION_STATE_CHANGED,
                    command_id=normalized.command_id,
                    detail=(
                        f"run status changed from {run.state.status.value} to {run_status.value}"
                    ),
                    resulting_run_revision=run.state.revision + 1,
                )
            )
            events.append(
                RunStatusChangedEvent(
                    event_id=uuid4(),
                    run_id=run.run_id,
                    occurred_at=now,
                    actor=normalized.actor,
                    kind=EventKind.RUN_STATUS_CHANGED,
                    previous=run.state.status,
                    current=run_status,
                    reason=reason,
                    cause_event_id=request_event_id,
                )
            )
        record = InterventionRecord.from_request(
            normalized,
            run_id=run.run_id,
            target_scope=scope,
            target_id=target_id,
            requested_at=now,
            validation_outcome="accepted",
            delivery_state=(
                ControlDeliveryStatus.PENDING if deliveries else ControlDeliveryStatus.NOT_REQUIRED
            ),
            deliveries=tuple(deliveries),
            resulting_run_revision=run.state.revision + 1,
        )
        next_active = tuple(
            item.stage_id
            for item in run.stages
            if item.status in {StageStatus.READY, StageStatus.RUNNING}
        )
        receipt = self.ledger.apply(
            LedgerMutation(
                command_id=normalized.command_id,
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=normalized.actor,
                occurred_at=now,
                run_update=RunProjectionUpdate(
                    status=run_status,
                    active_stages=next_active,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=(
                        reason if run_status == RunStatus.ATTENTION_REQUIRED else None
                    ),
                    resume_status=(
                        run.state.resume_status or run.state.status
                        if run_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                attempt_updates=tuple(attempt_updates),
                events=tuple(events),
                outbox_actions=tuple(outbox_actions),
                intervention_records=(record,),
                stage_redirects=tuple(stage_redirects),
            )
        )
        if receipt.outcome != CommandOutcome.ACCEPTED:
            return receipt
        await self.dispatch_pending(run.run_id)
        self.advance(run.run_id)
        return receipt

    def _intervention_target(self, request: Intervention) -> tuple[InterventionTargetScope, str]:
        if isinstance(request, (PauseIntervention, ResumeIntervention, StopIntervention)):
            scope, target = InterventionTargetScope.RUN, request.target
        elif isinstance(request, (StopAttemptIntervention, SteerIntervention, RetryIntervention)):
            scope = InterventionTargetScope.ATTEMPT
            target = request.attempt_id
            if request.target != target:
                raise ValueError("attempt intervention target must equal its exact attempt_id")
        elif isinstance(request, RedirectIntervention):
            scope = InterventionTargetScope.STAGE
            target = request.stage_id
            if request.target != target:
                raise ValueError("redirect target must equal its exact stage_id")
        else:
            raise ValueError(f"unsupported intervention kind {request.kind}")
        if request.target_scope is not None and request.target_scope != scope:
            raise ValueError("intervention target_scope does not match its command kind")
        return scope, target

    @staticmethod
    def _nominal_intervention_target(
        request: Intervention,
    ) -> tuple[InterventionTargetScope, str]:
        if isinstance(request, (PauseIntervention, ResumeIntervention, StopIntervention)):
            return InterventionTargetScope.RUN, request.target
        if isinstance(request, (StopAttemptIntervention, SteerIntervention, RetryIntervention)):
            return InterventionTargetScope.ATTEMPT, request.attempt_id
        if isinstance(request, RedirectIntervention):
            return InterventionTargetScope.STAGE, request.stage_id
        raise ValueError(f"unsupported intervention kind {request.kind}")

    def _record_rejected_intervention(
        self,
        request: Intervention,
        run: PersistedRun,
        scope: InterventionTargetScope,
        target_id: str,
        reason: str,
        *,
        expected_revision: int | None = None,
    ) -> CommandReceipt:
        now = self._now()
        request_event_id = uuid4()
        record = InterventionRecord.from_request(
            request,
            run_id=run.run_id,
            target_scope=scope,
            target_id=target_id,
            requested_at=now,
            validation_outcome="rejected",
            validation_detail=reason,
            resulting_run_revision=run.state.revision + 1,
        )
        return self.ledger.apply(
            LedgerMutation(
                command_id=request.command_id,
                run_id=run.run_id,
                expected_revision=(
                    expected_revision if expected_revision is not None else run.state.revision
                ),
                actor=request.actor,
                occurred_at=now,
                events=(
                    InterventionRequestedEvent(
                        event_id=request_event_id,
                        run_id=run.run_id,
                        occurred_at=now,
                        actor=request.actor,
                        kind=EventKind.INTERVENTION_REQUESTED,
                        intervention=request,
                    ),
                    InterventionLifecycleEvent(
                        event_id=uuid4(),
                        run_id=run.run_id,
                        occurred_at=now,
                        actor=request.actor,
                        kind=EventKind.INTERVENTION_REJECTED,
                        command_id=request.command_id,
                        detail=reason,
                        resulting_run_revision=run.state.revision + 1,
                    ),
                ),
                intervention_records=(record,),
                receipt_outcome=CommandOutcome.REJECTED,
                receipt_reason=reason,
            )
        )

    def _validate_intervention(self, request: Intervention, run: PersistedRun) -> None:
        if request.run_id != run.run_id or (
            request.target != run.run_id and request.target_scope == InterventionTargetScope.RUN
        ):
            raise ValueError("intervention run target does not match the persisted run")
        if run.state.status in {
            RunStatus.SUCCEEDED,
            RunStatus.FAILED,
            RunStatus.STOPPED,
        }:
            raise ValueError("terminal historical runs cannot be mutated in place")
        if isinstance(request, PauseIntervention):
            if run.state.status not in {RunStatus.READY, RunStatus.RUNNING}:
                raise ValueError("pause requires a ready or running run")
        elif isinstance(request, ResumeIntervention):
            if run.state.status != RunStatus.PAUSED:
                raise ValueError("resume requires a paused run")
        elif isinstance(request, StopIntervention):
            if run.state.status not in {
                RunStatus.READY,
                RunStatus.RUNNING,
                RunStatus.PAUSE_REQUESTED,
                RunStatus.PAUSED,
                RunStatus.ATTENTION_REQUIRED,
            }:
                raise ValueError("stop requires a nonterminal run")
        elif isinstance(request, StopAttemptIntervention):
            attempt = self._require_target_attempt(request.attempt_id, run)
            if attempt.state.status != AttemptStatus.RUNNING or not self._worker_handle(attempt):
                raise ValueError(
                    "selected attempt must be running with a persisted worker identity"
                )
        elif isinstance(request, SteerIntervention):
            attempt = self._require_target_attempt(request.attempt_id, run)
            if attempt.state.status != AttemptStatus.RUNNING or not self._worker_handle(attempt):
                raise ValueError("steering requires the exact running attempt and worker identity")
            if attempt.state.worker_turn_id != request.expected_turn_id:
                raise ValueError("steer command turn identity is stale")
            if attempt.state.input_revision_uncertain:
                raise ValueError("steering is blocked while a prior delivery is uncertain")
        elif isinstance(request, RetryIntervention):
            attempt = self._require_target_attempt(request.attempt_id, run)
            stage = self._stage(run, attempt.stage_id)
            lineage = self._ordered_lineage(
                [
                    item
                    for item in self.ledger.list_attempts(run.run_id, stage.id)
                    if item.slot_id == attempt.slot_id
                ]
            )
            profile = self._profile(run, attempt.spec.profile_id)
            if not lineage or lineage[-1].spec.attempt_id != attempt.spec.attempt_id:
                raise ValueError("only the latest attempt in a slot can be retried")
            if attempt.state.status not in {
                AttemptStatus.FAILED,
                AttemptStatus.TIMED_OUT,
                AttemptStatus.CANCELLED,
            }:
                raise ValueError("retry requires a known terminal failure or cancellation")
            if attempt.state.status == AttemptStatus.CANCELLED:
                if attempt.state.error_class not in profile.retry_policy.recoverable_classes:
                    raise ValueError("cancellation is not eligible under this profile retry policy")
            elif attempt.state.error_class not in profile.retry_policy.recoverable_classes:
                raise ValueError("failure class is not eligible under this profile retry policy")
            if profile.retry_policy.require_safe_retry and not attempt.state.safe_to_retry:
                raise ValueError("failure is not marked safe to retry")
            if not run.spec.workflow.policy.allow_retry:
                raise ValueError("workflow policy forbids retry")
            if len(lineage) >= min(
                profile.retry_policy.max_attempts, run.spec.workflow.max_attempts_per_slot
            ):
                raise ValueError("retry budget is exhausted")
            if self._elapsed(run) >= run.spec.workflow.max_duration_seconds:
                raise ValueError("workflow time budget is exhausted")
            if attempt.state.status == AttemptStatus.OUTCOME_UNKNOWN or any(
                item.state.status == AttemptStatus.OUTCOME_UNKNOWN
                for item in self.ledger.list_attempts(run.run_id, stage.id)
                if item.slot_id == attempt.slot_id
            ):
                raise ValueError("ambiguous attempt ownership cannot be retried")
            if any(
                item.status.value == "held" and item.attempt_id == attempt.spec.attempt_id
                for item in self.ledger.list_reservations(run.run_id)
            ):
                raise ValueError("attempt resource ownership is not settled")
        elif isinstance(request, RedirectIntervention):
            redirect_stage = next(
                (item for item in run.spec.workflow.stages if item.id == request.stage_id), None
            )
            projection = next(
                (item for item in run.stages if item.stage_id == request.stage_id), None
            )
            if redirect_stage is None or projection is None:
                raise ValueError("redirect stage does not exist in this run")
            if redirect_stage.slot_kind != SlotKind.SELECT_ONE:
                raise ValueError("redirect only supports select-one stages")
            if projection.status not in {StageStatus.PENDING, StageStatus.READY}:
                raise ValueError("redirect destination is active or completed")
            if self.ledger.list_attempts(run.run_id, redirect_stage.id):
                raise ValueError("redirect destination already has an attempt")
            allowed = next(
                (
                    item.allowed_profiles
                    for item in run.spec.workflow.allowed_redirects
                    if item.stage == redirect_stage.id
                ),
                (),
            )
            if request.recipient_profile_id not in allowed:
                raise ValueError("recipient is not declared in allowed_redirects")
            current_profile_id = self.ledger.get_stage_redirect(run.run_id, redirect_stage.id)
            if current_profile_id is None:
                selection = next(
                    item for item in run.spec.selections if item.stage_id == redirect_stage.id
                )
                current_profile_id = selection.profile_ids[0]
            current_profile = self._profile(run, current_profile_id)
            target_profile = self._profile(run, request.recipient_profile_id)
            if target_profile.required_outputs != current_profile.required_outputs:
                raise ValueError("recipient has an incompatible output contract")
            if not target_profile.permissions.is_within(current_profile.permissions):
                raise ValueError("redirect would expand the current permission set")

    def _require_target_attempt(self, attempt_id: str, run: PersistedRun) -> PersistedAttempt:
        try:
            attempt = self.ledger.get_attempt(attempt_id)
        except KeyError as error:
            raise ValueError(f"unknown target attempt {attempt_id}") from error
        if attempt.spec.run_id != run.run_id:
            raise ValueError("target attempt belongs to another run")
        return attempt

    @staticmethod
    def _worker_handle(attempt: PersistedAttempt) -> WorkerHandle | None:
        state = attempt.state
        if not all(
            (
                state.worker_handle_id,
                state.worker_backend_version,
                state.worker_lifecycle_owner_id,
            )
        ):
            return None
        assert state.worker_handle_id is not None
        assert state.worker_backend_version is not None
        assert state.worker_lifecycle_owner_id is not None
        return WorkerHandle(
            handle_id=state.worker_handle_id,
            backend=attempt.spec.backend,
            backend_version=state.worker_backend_version,
            attempt_id=attempt.spec.attempt_id,
            session_id=state.worker_session_id,
            thread_id=state.worker_thread_id,
            turn_id=state.worker_turn_id,
            lifecycle_owner_id=state.worker_lifecycle_owner_id,
        )

    def _add_interrupt_intent(
        self,
        request: StopIntervention | StopAttemptIntervention,
        attempt: PersistedAttempt,
        requested_at: datetime,
        outbox_actions: list[OutboxIntent],
        deliveries: list[ControlDelivery],
        attempt_updates: list[AttemptState],
    ) -> None:
        handle = self._worker_handle(attempt)
        if attempt.state.status != AttemptStatus.RUNNING or handle is None:
            raise ValueError("interrupt requires an exact running attempt with persisted identity")
        action_id = uuid4()
        delivery = ControlDelivery(
            action_id=action_id,
            attempt_id=attempt.spec.attempt_id,
            status=ControlDeliveryStatus.PENDING,
            requested_at=requested_at,
            worker_handle_id=handle.handle_id,
            worker_thread_id=handle.thread_id,
            worker_turn_id=handle.turn_id,
        )
        deliveries.append(delivery)
        outbox_actions.append(
            OutboxIntent(
                action_id=action_id,
                action_key=f"control:{request.command_id}:{attempt.spec.attempt_id}:interrupt",
                kind="interrupt_attempt",
                payload={
                    "command_id": str(request.command_id),
                    "attempt_id": attempt.spec.attempt_id,
                    "expected_turn_id": handle.turn_id,
                    "timeout": (
                        isinstance(request, StopAttemptIntervention) and request.reason == "timeout"
                    ),
                },
            )
        )
        attempt_updates.append(
            attempt.state.model_copy(
                update={"status": AttemptStatus.CANCEL_REQUESTED, "retry_authorized": False}
            )
        )

    def _has_unclaimed_launch(self, run_id: str, attempt_id: str) -> bool:
        return any(
            action.kind == "launch_attempt"
            and action.status == OutboxStatus.PENDING
            and action.payload.get("attempt_id") == attempt_id
            for action in self.ledger.list_outbox_actions(run_id)
        )

    @staticmethod
    def _steered_input_revision(attempt: PersistedAttempt, request: SteerIntervention) -> str:
        previous = attempt.state.effective_input_revision or content_hash(
            canonical_json(attempt.spec.input_manifest)
        )
        return content_hash(
            canonical_json(
                {
                    "previous_input_revision": previous,
                    "command_id": str(request.command_id),
                    "instruction": request.instruction,
                    "expected_turn_id": request.expected_turn_id,
                }
            )
        )

    async def _bounded_call(self, awaitable: Awaitable[object]) -> tuple[bool, object | None]:
        """Bound a backend control call using the deterministic clock."""
        task = asyncio.ensure_future(awaitable)
        deadline = self.clock.now + self.control_timeout_seconds
        while True:
            if self.clock.now >= deadline:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                return False, None
            clock_task = asyncio.create_task(self.clock.wait_until_advanced(self.clock.now))
            done, _pending = await asyncio.wait(
                (task, clock_task), return_when=asyncio.FIRST_COMPLETED
            )
            if task in done:
                clock_task.cancel()
                await asyncio.gather(clock_task, return_exceptions=True)
                return True, task.result()
            await clock_task

    async def _dispatch_control_action(self, action: OutboxAction) -> None:
        attempt_id = str(action.payload.get("attempt_id", ""))
        try:
            attempt = self.ledger.get_attempt(attempt_id)
        except KeyError:
            self._record_orphan_control_unknown(action, "control references a missing attempt")
            return
        handle = self._worker_handle(attempt)
        if handle is None:
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                "worker identity is unavailable for control delivery",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=True,
                attention_reason="worker control target cannot be identified safely",
            )
            return

        self._mark_control_delivery_attempted(action)
        try:
            if action.kind == "steer_attempt":
                result = await self._bounded_call(
                    self.backend.steer(
                        handle,
                        SteerCommand(
                            command_id=action.action_id,
                            attempt_id=attempt_id,
                            expected_turn_id=str(action.payload.get("expected_turn_id", "")),
                            instruction=str(action.payload.get("instruction", "")),
                            effective_input_revision=str(
                                action.payload.get("effective_input_revision", "")
                            ),
                        ),
                    )
                )
            elif action.kind == "interrupt_attempt":
                result = await self._bounded_call(self.backend.interrupt(handle, action.action_id))
            else:
                self._finish_control_delivery(
                    action,
                    ControlDeliveryStatus.UNSUPPORTED,
                    f"unsupported outbox action {action.kind}",
                    outbox_status=OutboxStatus.REJECTED,
                    attention_reason="a required control action is unsupported",
                )
                return
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                f"control delivery outcome is uncertain: {type(error).__name__}",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=action.kind == "interrupt_attempt",
                mark_input_uncertain=action.kind == "steer_attempt",
                attention_reason="control delivery outcome is unresolved",
            )
            await self._inspect_attempt(attempt_id, action.command_id)
            return

        completed, raw_ack = result
        if not completed:
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                "control acknowledgement exceeded the bounded timeout",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=action.kind == "interrupt_attempt",
                mark_input_uncertain=action.kind == "steer_attempt",
                attention_reason="control acknowledgement is unresolved",
            )
            await self._inspect_attempt(attempt_id, action.command_id)
            return
        assert isinstance(raw_ack, ControlAck)
        if raw_ack.command_id != action.action_id:
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                "backend acknowledgement command identity did not match",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=action.kind == "interrupt_attempt",
                mark_input_uncertain=action.kind == "steer_attempt",
                attention_reason="backend control acknowledgement identity is uncertain",
            )
            await self._inspect_attempt(attempt_id, action.command_id)
            return
        if not raw_ack.accepted:
            status = (
                ControlDeliveryStatus.UNSUPPORTED
                if not raw_ack.supported
                else ControlDeliveryStatus.REJECTED
            )
            self._finish_control_delivery(
                action,
                status,
                raw_ack.reason or "backend rejected control",
                outbox_status=OutboxStatus.REJECTED,
                restore_running=action.kind == "interrupt_attempt",
                attention_reason=(
                    "required worker interruption was rejected"
                    if action.kind == "interrupt_attempt"
                    and raw_ack.reason != "worker already terminal"
                    else None
                ),
            )
            if raw_ack.reason == "worker already terminal":
                await self._inspect_attempt(attempt_id, action.command_id)
            return

        if action.kind == "steer_attempt":
            current_attempt = self.ledger.get_attempt(attempt_id)
            if current_attempt.state.status not in {
                AttemptStatus.RUNNING,
                AttemptStatus.CANCEL_REQUESTED,
            }:
                self._finish_control_delivery(
                    action,
                    ControlDeliveryStatus.REJECTED,
                    "worker completed before the steering acknowledgement was committed",
                    outbox_status=OutboxStatus.REJECTED,
                )
                await self._inspect_attempt(attempt_id, action.command_id)
                return
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.ACKNOWLEDGED,
                "worker acknowledged the scoped steering input",
                outbox_status=OutboxStatus.ACKNOWLEDGED,
                effective_input_revision=str(action.payload["effective_input_revision"]),
            )
            return

        try:
            close_ok, raw_receipt = await self._bounded_call(self.backend.close(handle))
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                f"worker close outcome is uncertain: {type(error).__name__}",
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=True,
                attention_reason="worker ownership remains unresolved after stop request",
            )
            await self._inspect_attempt(attempt_id, action.command_id)
            return
        if not close_ok or not isinstance(raw_receipt, ShutdownReceipt) or not raw_receipt.settled:
            detail = (
                "worker interrupt was acknowledged but bounded close did not settle ownership"
                if close_ok
                else "worker interrupt was acknowledged but bounded close timed out"
            )
            self._finish_control_delivery(
                action,
                ControlDeliveryStatus.UNKNOWN,
                detail,
                outbox_status=OutboxStatus.UNKNOWN,
                mark_unknown_attempt=True,
                attention_reason="worker ownership remains unresolved after stop request",
            )
            await self._inspect_attempt(attempt_id, action.command_id)
            return
        self._finish_control_delivery(
            action,
            ControlDeliveryStatus.ACKNOWLEDGED,
            raw_receipt.detail or "worker interruption and close settled",
            outbox_status=OutboxStatus.ACKNOWLEDGED,
            settle_attempt=True,
        )

    def _mark_control_delivery_attempted(self, action: OutboxAction) -> None:
        self._finish_control_delivery(
            action,
            ControlDeliveryStatus.DELIVERING,
            "control delivery started",
            outbox_status=None,
        )

    def _finish_control_delivery(
        self,
        action: OutboxAction,
        status: ControlDeliveryStatus,
        detail: str,
        *,
        outbox_status: OutboxStatus | None,
        mark_unknown_attempt: bool = False,
        mark_input_uncertain: bool = False,
        restore_running: bool = False,
        effective_input_revision: str | None = None,
        settle_attempt: bool = False,
        attention_reason: str | None = None,
    ) -> None:
        attempt_id = str(action.payload.get("attempt_id", ""))

        def build(run: PersistedRun) -> LedgerMutation:
            records = self.ledger.list_intervention_records(run.run_id)
            prior_record = next(
                (item for item in records if item.command_id == action.command_id), None
            )
            if prior_record is None:
                raise LedgerInvariantError("control action has no persisted intervention record")
            now = self._now()
            updated_deliveries: list[ControlDelivery] = []
            found = False
            for delivery in prior_record.deliveries:
                if delivery.action_id != action.action_id:
                    updated_deliveries.append(delivery)
                    continue
                found = True
                updated_deliveries.append(
                    delivery.model_copy(
                        update={
                            "status": status,
                            "attempted_at": delivery.attempted_at or now,
                            "completed_at": (
                                None
                                if status
                                in {ControlDeliveryStatus.PENDING, ControlDeliveryStatus.DELIVERING}
                                else now
                            ),
                            "detail": detail,
                            "effective_input_revision": (
                                effective_input_revision or delivery.effective_input_revision
                            ),
                        }
                    )
                )
            if not found:
                raise LedgerInvariantError("intervention record has no matching delivery")
            delivery_state = self._aggregate_delivery_state(tuple(updated_deliveries))
            updated_record = prior_record.model_copy(
                update={
                    "delivery_state": delivery_state,
                    "deliveries": tuple(updated_deliveries),
                    "resulting_run_revision": run.state.revision + 1,
                    "resulting_attempt_revision": effective_input_revision
                    or prior_record.resulting_attempt_revision,
                }
            )
            current_attempt = self.ledger.get_attempt(attempt_id)
            attempt_update: AttemptState | None = None
            releases: tuple[ReservationChange, ...] = ()
            next_status = run.state.status
            next_attention = run.state.attention_reason
            next_resume = run.state.resume_status
            if settle_attempt and current_attempt.state.status in _ACTIVE_ATTEMPT_STATES:
                timeout = bool(action.payload.get("timeout"))
                terminal_status = AttemptStatus.TIMED_OUT if timeout else AttemptStatus.CANCELLED
                attempt_update = current_attempt.state.model_copy(
                    update={
                        "status": terminal_status,
                        "finished_at": now,
                        "error_class": FailureClass.TIMEOUT if timeout else FailureClass.CANCELLED,
                        "error_summary": detail,
                        "safe_to_retry": True,
                        "retry_authorized": False,
                    }
                )
                releases = self._reservation_releases(run.run_id, attempt_id)
                if prior_record.kind == InterventionKind.STOP_ATTEMPT and not timeout:
                    next_status = RunStatus.ATTENTION_REQUIRED
                    next_attention = (
                        "selected attempt was cancelled; its required slot is unresolved"
                    )
                    next_resume = run.state.resume_status or run.state.status
                elif timeout:
                    next_status = run.state.resume_status or RunStatus.RUNNING
                    if next_status == RunStatus.ATTENTION_REQUIRED:
                        next_status = RunStatus.RUNNING
                    next_attention = None
                    next_resume = None
                else:
                    next_status = self._status_after_settlement(run, attempt_id)
                    if next_status != RunStatus.ATTENTION_REQUIRED:
                        next_attention = None
                        next_resume = None
            elif mark_unknown_attempt and current_attempt.state.status in _ACTIVE_ATTEMPT_STATES:
                attempt_update = current_attempt.state.model_copy(
                    update={
                        "status": AttemptStatus.OUTCOME_UNKNOWN,
                        "error_summary": detail,
                        "safe_to_retry": False,
                    }
                )
            elif restore_running and current_attempt.state.status == AttemptStatus.CANCEL_REQUESTED:
                attempt_update = current_attempt.state.model_copy(
                    update={"status": AttemptStatus.RUNNING, "error_summary": detail}
                )
            elif mark_input_uncertain:
                attempt_update = current_attempt.state.model_copy(
                    update={"input_revision_uncertain": True, "error_summary": detail}
                )
            elif (
                effective_input_revision is not None
                and prior_record.kind == InterventionKind.STEER
                and current_attempt.state.status
                in {AttemptStatus.RUNNING, AttemptStatus.CANCEL_REQUESTED}
            ):
                attempt_update = current_attempt.state.model_copy(
                    update={
                        "effective_input_revision": effective_input_revision,
                        "input_revision_uncertain": False,
                        "error_summary": None,
                    }
                )
            if attention_reason is not None:
                next_status = RunStatus.ATTENTION_REQUIRED
                next_attention = attention_reason
                next_resume = run.state.resume_status or run.state.status

            event_kind = {
                ControlDeliveryStatus.DELIVERING: EventKind.INTERVENTION_DELIVERY_ATTEMPTED,
                ControlDeliveryStatus.ACKNOWLEDGED: EventKind.INTERVENTION_DELIVERY_ACKNOWLEDGED,
                ControlDeliveryStatus.UNSUPPORTED: EventKind.INTERVENTION_DELIVERY_UNSUPPORTED,
                ControlDeliveryStatus.REJECTED: EventKind.INTERVENTION_DELIVERY_FAILED,
                ControlDeliveryStatus.FAILED: EventKind.INTERVENTION_DELIVERY_FAILED,
                ControlDeliveryStatus.UNKNOWN: EventKind.INTERVENTION_DELIVERY_UNKNOWN,
                ControlDeliveryStatus.PENDING: EventKind.INTERVENTION_DELIVERY_ATTEMPTED,
                ControlDeliveryStatus.NOT_REQUIRED: EventKind.INTERVENTION_DELIVERY_ATTEMPTED,
            }[status]
            events: list[Event] = [
                InterventionLifecycleEvent(
                    event_id=uuid4(),
                    run_id=run.run_id,
                    occurred_at=now,
                    actor=self.actor,
                    kind=cast(Any, event_kind),
                    command_id=action.command_id,
                    attempt_id=attempt_id,
                    action_id=action.action_id,
                    detail=detail,
                    resulting_run_revision=run.state.revision + 1,
                )
            ]
            if next_status != run.state.status:
                events.append(
                    RunStatusChangedEvent(
                        event_id=uuid4(),
                        run_id=run.run_id,
                        occurred_at=now,
                        actor=self.actor,
                        kind=EventKind.RUN_STATUS_CHANGED,
                        previous=run.state.status,
                        current=next_status,
                        reason=next_attention or detail,
                        cause_event_id=events[0].event_id,
                    )
                )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=now,
                run_update=(
                    RunProjectionUpdate(
                        status=next_status,
                        elapsed_seconds=self._elapsed(run),
                        attention_reason=next_attention,
                        resume_status=next_resume,
                    )
                    if next_status != run.state.status or settle_attempt or attention_reason
                    else None
                ),
                attempt_updates=(attempt_update,) if attempt_update is not None else (),
                events=tuple(events),
                outbox_outcomes=(
                    OutboxOutcomeChange(
                        action_id=action.action_id,
                        status=outbox_status,
                        result=detail,
                    ),
                )
                if outbox_status is not None
                else (),
                reservations=releases,
                intervention_records=(updated_record,),
            )

        self._commit(action.run_id, build)

    @staticmethod
    def _aggregate_delivery_state(deliveries: tuple[ControlDelivery, ...]) -> ControlDeliveryStatus:
        states = {item.status for item in deliveries}
        if ControlDeliveryStatus.UNKNOWN in states:
            return ControlDeliveryStatus.UNKNOWN
        if ControlDeliveryStatus.PENDING in states or ControlDeliveryStatus.DELIVERING in states:
            return ControlDeliveryStatus.PENDING
        if ControlDeliveryStatus.UNSUPPORTED in states:
            return ControlDeliveryStatus.UNSUPPORTED
        if ControlDeliveryStatus.FAILED in states:
            return ControlDeliveryStatus.FAILED
        if ControlDeliveryStatus.REJECTED in states:
            return ControlDeliveryStatus.REJECTED
        return ControlDeliveryStatus.ACKNOWLEDGED

    def _record_orphan_control_unknown(self, action: OutboxAction, detail: str) -> None:
        try:
            self.ledger.record_outbox_outcome(
                action.action_id,
                uuid4(),
                self.ledger.get_run(action.run_id).state.revision,
                OutboxStatus.UNKNOWN,
                result=detail,
                actor=self.actor,
                occurred_at=self._now(),
            )
        except BaseException:
            return

    def mark_claimed_launches_unknown(self, run_id: str | None = None) -> int:
        """On coordinator restart, retain possibly launched work without replaying it."""
        marked = 0
        for action in self.ledger.list_outbox_actions(run_id):
            if action.status not in {OutboxStatus.CLAIMED, OutboxStatus.ACKNOWLEDGED}:
                continue
            if action.kind != "launch_attempt":
                continue
            attempt_id = str(action.payload.get("attempt_id", ""))
            try:
                attempt = self.ledger.get_attempt(attempt_id)
            except KeyError:
                continue
            if attempt.state.status not in {
                AttemptStatus.LAUNCHING,
                AttemptStatus.RUNNING,
                AttemptStatus.CANCEL_REQUESTED,
            }:
                continue
            worker = self._workers.get(attempt_id)
            if worker is not None and not worker.done():
                continue
            self._mark_unknown_launch(
                action.action_id, attempt, "possibly launched worker survived coordinator restart"
            )
            marked += 1
        return marked

    async def _consume(self, attempt_id: str, handle: WorkerHandle) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        run = self.ledger.get_run(attempt.spec.run_id)
        profile = self._profile(run, attempt.spec.profile_id)
        started_at = attempt.state.started_at or self._now()
        deadline = started_at.timestamp() + profile.timeout_seconds
        stream = self.backend.events(handle)
        sequence = 0
        try:
            while True:
                event_task: asyncio.Future[WorkerEvent] = asyncio.ensure_future(anext(stream))
                clock_task = asyncio.create_task(self.clock.wait_until_advanced(self.clock.now))
                done, pending = await asyncio.wait(
                    (event_task, clock_task), return_when=asyncio.FIRST_COMPLETED
                )
                if event_task in done:
                    clock_task.cancel()
                    try:
                        await clock_task
                    except asyncio.CancelledError:
                        pass
                    try:
                        event = event_task.result()
                    except StopAsyncIteration:
                        self._mark_unknown_launch(
                            self._action_for_attempt(attempt_id),
                            self.ledger.get_attempt(attempt_id),
                            "worker event stream ended without a terminal event",
                        )
                        return
                    if event.attempt_id != attempt_id and isinstance(event, WorkerTerminalEvent):
                        self._settle_terminal(attempt_id, event)
                        return
                    sequence = self._validate_event_order(event, attempt_id, sequence)
                    if isinstance(event, (WorkerStartedEvent, WorkerProgressEvent)):
                        continue
                    if isinstance(event, WorkerDisconnectedEvent):
                        self._mark_unknown_launch(
                            self._action_for_attempt(attempt_id),
                            self.ledger.get_attempt(attempt_id),
                            f"worker disconnected: {event.reason}",
                        )
                        return
                    if isinstance(event, WorkerFailureEvent):
                        self._settle_worker_failure(attempt_id, event)
                        return
                    if isinstance(event, WorkerTerminalEvent):
                        self._settle_terminal(attempt_id, event)
                        return
                    self._mark_unknown_launch(
                        self._action_for_attempt(attempt_id),
                        self.ledger.get_attempt(attempt_id),
                        f"unsupported worker event {event.kind}",
                    )
                    return

                event_task.cancel()
                try:
                    await event_task
                except (asyncio.CancelledError, StopAsyncIteration):
                    pass
                if self._now().timestamp() >= deadline:
                    current_run = self.ledger.get_run(attempt.spec.run_id)
                    await self.apply_intervention(
                        StopAttemptIntervention(
                            command_id=uuid4(),
                            actor=self.actor,
                            target=attempt_id,
                            expected_run_revision=current_run.state.revision,
                            kind=InterventionKind.STOP_ATTEMPT,
                            run_id=current_run.run_id,
                            target_scope=InterventionTargetScope.ATTEMPT,
                            attempt_id=attempt_id,
                            reason="timeout",
                        )
                    )
                    return
                for task in pending:
                    if task is not event_task:
                        task.cancel()
        except asyncio.CancelledError:
            raise
        except BaseException as error:
            self._mark_unknown_launch(
                self._action_for_attempt(attempt_id),
                self.ledger.get_attempt(attempt_id),
                f"worker stream outcome is unknown: {type(error).__name__}",
            )

    @staticmethod
    def _validate_event_order(event: WorkerEvent, attempt_id: str, previous: int) -> int:
        if event.attempt_id != attempt_id:
            raise ValueError("worker event belongs to another attempt")
        if event.sequence <= previous:
            raise ValueError("worker event sequence is not strictly increasing")
        return event.sequence

    def _settle_terminal(
        self,
        attempt_id: str,
        event: WorkerTerminalEvent,
        *,
        reconciliation_event: InterventionLifecycleEvent | None = None,
        reconciliation: Reconciliation | None = None,
    ) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        if attempt.state.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            return
        run = self.ledger.get_run(attempt.spec.run_id)
        if reconciliation_event is None and attempt.state.status == AttemptStatus.OUTCOME_UNKNOWN:
            reconciliation_event = InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=run.run_id,
                occurred_at=self._now(),
                actor=self.actor,
                kind=EventKind.RECONCILIATION_RESOLVED,
                command_id=uuid4(),
                attempt_id=attempt_id,
                detail="worker terminal event resolved previously ambiguous ownership",
                reconciled_status=AttemptStatus.SUCCEEDED,
                reconciliation_known=True,
            )
        stage = self._stage(run, attempt.stage_id)
        result: WorkerResult | None = None
        validation_error: str | None = None
        try:
            result = WorkerResult.model_validate(event.result.model_dump(mode="json"))
            if event.attempt_id != attempt_id or result.attempt_id != attempt_id:
                raise ValueError("terminal result attempt identity does not match launch")
            expected_input = content_hash(canonical_json(attempt.spec.input_manifest))
            known_input = attempt.state.effective_input_revision or expected_input
            if attempt.state.input_revision_uncertain:
                requested_revisions = {
                    delivery.effective_input_revision
                    for record in self.ledger.list_intervention_records(run.run_id)
                    if record.kind == InterventionKind.STEER
                    for delivery in record.deliveries
                    if delivery.attempt_id == attempt_id
                    and delivery.effective_input_revision is not None
                }
                if (
                    reconciliation is None
                    or reconciliation.effective_input_revision not in requested_revisions
                ):
                    raise ValueError(
                        "terminal result cannot satisfy completion while "
                        "steering input is uncertain"
                    )
                known_input = reconciliation.effective_input_revision
            accepted_revisions = {known_input}
            if reconciliation is not None and reconciliation.effective_input_revision:
                accepted_revisions.add(reconciliation.effective_input_revision)
            if result.input_revision not in accepted_revisions:
                raise ValueError("terminal result uses a stale or incorrect input revision")
            if (
                attempt.spec.workspace_revision
                and result.workspace_revision != attempt.spec.workspace_revision
            ):
                raise ValueError("terminal result does not verify the requested workspace revision")
            required = set(stage.required_outputs) | set(
                self._profile(run, attempt.spec.profile_id).required_outputs
            )
            names = [item.name for item in result.artifacts]
            if len(names) != len(set(names)):
                raise ValueError("artifact envelope contains duplicate output names")
            missing = sorted(required - set(names))
            if missing and result.status != OutputStatus.BLOCKED:
                raise ValueError(
                    f"artifact envelope is missing required outputs: {', '.join(missing)}"
                )
            for artifact in result.artifacts:
                if not _SHA256.fullmatch(artifact.content_hash):
                    raise ValueError(f"output {artifact.name} has an invalid SHA-256 content hash")
                if artifact.relative_path and (
                    artifact.relative_path.startswith("/")
                    or ".." in artifact.relative_path.split("/")
                    or "\\" in artifact.relative_path
                ):
                    raise ValueError(f"output {artifact.name} has an unsafe relative path")
        except (ValidationError, ValueError):
            validation_error = "invalid artifact-envelope-v1 result"

        if validation_error:
            self._settle_failure(
                attempt_id,
                AttemptStatus.FAILED,
                FailureClass.INVALID_OUTPUT,
                validation_error,
                safe_to_retry=False,
                result_registration=AttemptResultRegistration(
                    attempt_id=attempt_id, validation_error=validation_error
                ),
                reconciliation_event=reconciliation_event,
            )
            return

        assert result is not None
        self._settle_success(attempt_id, result, reconciliation_event=reconciliation_event)

    def _settle_success(
        self,
        attempt_id: str,
        result: WorkerResult,
        *,
        reconciliation_event: InterventionLifecycleEvent | None = None,
    ) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        if attempt.state.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            return
        reservations = self._reservation_releases(attempt.spec.run_id, attempt_id)

        def build(run: PersistedRun) -> LedgerMutation:
            latest_attempt = self.ledger.get_attempt(attempt_id)
            finished = self._now()
            state = latest_attempt.state.model_copy(
                update={
                    "status": AttemptStatus.SUCCEEDED,
                    "finished_at": finished,
                    "receipt_id": f"worker:{attempt_id}",
                    "effective_input_revision": result.input_revision,
                    "input_revision_uncertain": False,
                }
            )
            next_status = (
                self._status_after_reconciliation(run, attempt_id, AttemptStatus.SUCCEEDED)
                if reconciliation_event is not None
                else self._status_after_settlement(run, attempt_id)
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=finished,
                run_update=RunProjectionUpdate(
                    status=next_status,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=(
                        run.state.attention_reason
                        if next_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                    resume_status=(
                        run.state.resume_status
                        if next_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                attempt_updates=(state,),
                attempt_results=(AttemptResultRegistration(attempt_id=attempt_id, result=result),),
                reservations=reservations,
                events=(reconciliation_event,) if reconciliation_event is not None else (),
            )

        self._commit(attempt.spec.run_id, build)

    def _settle_worker_failure(self, attempt_id: str, event: WorkerFailureEvent) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        reconciliation_event = None
        if attempt.state.status == AttemptStatus.OUTCOME_UNKNOWN:
            reconciliation_event = InterventionLifecycleEvent(
                event_id=uuid4(),
                run_id=attempt.spec.run_id,
                occurred_at=self._now(),
                actor=self.actor,
                kind=EventKind.RECONCILIATION_RESOLVED,
                command_id=uuid4(),
                attempt_id=attempt_id,
                detail="worker failure event resolved previously ambiguous ownership",
                reconciled_status=AttemptStatus.FAILED,
                reconciliation_known=True,
            )
        self._settle_failure(
            attempt_id,
            AttemptStatus.FAILED,
            event.failure_class,
            event.summary,
            safe_to_retry=event.safe_to_retry,
            reconciliation_event=reconciliation_event,
        )

    def _settle_launch_failure(
        self,
        action_id: UUID,
        attempt: PersistedAttempt,
        failure_class: FailureClass,
        summary: str,
        *,
        safe_to_retry: bool,
    ) -> None:
        releases = self._reservation_releases(attempt.spec.run_id, attempt.spec.attempt_id)

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            failed = current.state.model_copy(
                update={
                    "status": AttemptStatus.FAILED,
                    "finished_at": self._now(),
                    "error_class": failure_class,
                    "error_summary": summary,
                    "safe_to_retry": safe_to_retry,
                }
            )
            next_status = self._status_after_settlement(run, attempt.spec.attempt_id)
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=next_status,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=(
                        run.state.attention_reason
                        if next_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                    resume_status=(
                        run.state.resume_status
                        if next_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                attempt_updates=(failed,),
                outbox_outcomes=(
                    OutboxOutcomeChange(
                        action_id=action_id,
                        status=OutboxStatus.REJECTED,
                        result=summary,
                    ),
                ),
                reservations=releases,
            )

        self._commit(attempt.spec.run_id, build)

    def _settle_failure(
        self,
        attempt_id: str,
        status: AttemptStatus,
        failure_class: FailureClass,
        summary: str,
        *,
        safe_to_retry: bool,
        result_registration: AttemptResultRegistration | None = None,
        run_status: RunStatus | None = None,
        reconciliation_event: InterventionLifecycleEvent | None = None,
    ) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        if attempt.state.status in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            return
        releases = (
            self._reservation_releases(attempt.spec.run_id, attempt_id)
            if status in {AttemptStatus.FAILED, AttemptStatus.TIMED_OUT, AttemptStatus.CANCELLED}
            else ()
        )

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt_id)
            failed = current.state.model_copy(
                update={
                    "status": status,
                    "finished_at": self._now(),
                    "error_class": failure_class,
                    "error_summary": summary,
                    "safe_to_retry": safe_to_retry,
                }
            )
            next_status = run_status or (
                self._status_after_reconciliation(run, attempt_id, status)
                if reconciliation_event is not None
                else self._status_after_settlement(run, attempt_id)
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=next_status,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=(
                        summary if next_status == RunStatus.ATTENTION_REQUIRED else None
                    ),
                    resume_status=(
                        run.state.resume_status or run.state.status
                        if next_status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                attempt_updates=(failed,),
                attempt_results=(result_registration,) if result_registration else (),
                reservations=releases,
                events=(reconciliation_event,) if reconciliation_event is not None else (),
            )

        self._commit(attempt.spec.run_id, build)

    def _mark_unknown_launch(
        self, action_id: UUID, attempt: PersistedAttempt, summary: str
    ) -> None:
        if attempt.state.status in {
            AttemptStatus.OUTCOME_UNKNOWN,
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.TIMED_OUT,
            AttemptStatus.CANCELLED,
        }:
            return

        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            uncertain = current.state.model_copy(
                update={
                    "status": AttemptStatus.OUTCOME_UNKNOWN,
                    "error_summary": summary,
                    "safe_to_retry": False,
                }
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=RunStatus.ATTENTION_REQUIRED,
                    elapsed_seconds=self._elapsed(run),
                    attention_reason=(
                        summary
                        if summary.startswith("reconciliation pending:")
                        else f"reconciliation pending: {summary}"
                    ),
                    resume_status=run.state.resume_status or run.state.status,
                ),
                attempt_updates=(uncertain,),
                outbox_outcomes=(
                    OutboxOutcomeChange(
                        action_id=action_id,
                        status=OutboxStatus.UNKNOWN,
                        result=summary,
                    ),
                )
                if any(
                    item.action_id == action_id and item.status == OutboxStatus.CLAIMED
                    for item in self.ledger.list_outbox_actions(run.run_id)
                )
                else (),
            )

        self._commit(attempt.spec.run_id, build)

    def _acknowledge_launch(
        self, action_id: UUID, attempt: PersistedAttempt, handle: WorkerHandle
    ) -> None:
        def build(run: PersistedRun) -> LedgerMutation:
            current = self.ledger.get_attempt(attempt.spec.attempt_id)
            started = self._now()
            running = current.state.model_copy(
                update={
                    "status": AttemptStatus.RUNNING,
                    "started_at": started,
                    "receipt_id": handle.handle_id,
                    "worker_handle_id": handle.handle_id,
                    "worker_backend_version": handle.backend_version,
                    "worker_session_id": handle.session_id,
                    "worker_thread_id": handle.thread_id,
                    "worker_turn_id": handle.turn_id,
                    "worker_lifecycle_owner_id": handle.lifecycle_owner_id,
                }
            )
            if current.state.worker_lifecycle_owner_id not in {
                None,
                handle.lifecycle_owner_id,
            }:
                raise LedgerInvariantError("launched worker differs from its durable owner intent")
            run_status = run.state.status
            if run_status in {RunStatus.READY, RunStatus.RUNNING}:
                run_status = RunStatus.RUNNING

            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=started,
                run_update=RunProjectionUpdate(
                    status=run_status,
                    elapsed_seconds=self._elapsed(run),
                ),
                attempt_updates=(running,),
                outbox_outcomes=(
                    OutboxOutcomeChange(
                        action_id=action_id,
                        status=OutboxStatus.ACKNOWLEDGED,
                        result=handle.handle_id,
                    ),
                ),
            )

        self._commit(attempt.spec.run_id, build)

    def _schedule_one_slot(
        self,
        run: PersistedRun,
        stage: ResolvedStage,
        *,
        repair_decision: str | None,
    ) -> bool:
        decision_question = next(
            (
                question
                for question in run.spec.workflow.policy.decision_questions
                if question.stage_id == stage.id
            ),
            None,
        )
        explicit_profile_override = any(
            item.path == f"stage.{stage.id}.profile" for item in run.spec.applied_overrides
        )
        if decision_question is not None and not explicit_profile_override:
            redirect_profile = self.ledger.get_stage_redirect(run.run_id, stage.id)
            redirect_record = self.ledger.get_stage_redirect_record(run.run_id, stage.id)
            records = self.ledger.list_decision_records(run.run_id)
            decision_record = next(
                (
                    item
                    for item in reversed(records)
                    if item.question_id == decision_question.question_id
                ),
                None,
            )
            if redirect_profile is None:
                return False
            allowed = self._decision_outcome_ids(run, stage.id)
            if redirect_profile not in allowed:
                raise LedgerInvariantError(
                    f"decision redirect {redirect_profile!r} is outside the frozen allowlist"
                )
            if decision_record is not None:
                disposition = decision_record.disposition
                if (
                    redirect_record is not None
                    and redirect_record.command_id == decision_record.decision_id
                    and (
                        decision_record.completed_at is None
                        or disposition is None
                        or disposition.status
                        not in {
                            DecisionDispositionStatus.ACCEPTED,
                            DecisionDispositionStatus.FALLBACK,
                        }
                        or disposition.selected_outcome_id != redirect_profile
                    )
                ):
                    return False
        slots = resolve_stage_slots(
            run,
            stage,
            redirected_profile_id=self.ledger.get_stage_redirect(run.run_id, stage.id),
        )
        attempts = self.ledger.list_attempts(run.run_id, stage.id)
        by_slot: dict[str, list[PersistedAttempt]] = {slot_id: [] for slot_id, _ in slots}
        for attempt in attempts:
            by_slot.setdefault(attempt.slot_id, []).append(attempt)

        for slot_index, (slot_id, profile_id) in enumerate(slots, start=1):
            lineage = self._ordered_lineage(by_slot.get(slot_id, []))
            if lineage and lineage[-1].state.status in _ACTIVE_ATTEMPT_STATES:
                continue
            if lineage and lineage[-1].state.status == AttemptStatus.SUCCEEDED:
                continue
            parent = lineage[-1] if lineage else None
            ordinal = len(lineage) + 1
            if parent is not None and not self._retry_allowed(run, stage, profile_id, lineage):
                self._update_stage(
                    run,
                    StageUpdate(stage_id=stage.id, status=StageStatus.FAILED),
                    status=RunStatus.RUNNING,
                    reason=f"slot {slot_id} exhausted its approved retry budget",
                )
                return True
            if self._elapsed(run) >= run.spec.workflow.max_duration_seconds:
                self._update_stage(
                    run,
                    StageUpdate(stage_id=stage.id, status=StageStatus.FAILED),
                    status=RunStatus.RUNNING,
                    reason="workflow duration budget is exhausted",
                )
                return True
            inputs, workspace_revision = resolve_stage_inputs(
                run, stage, repair_decision=repair_decision
            )
            profile = self._profile(run, profile_id)
            attempt_id = str(uuid5(NAMESPACE_URL, f"{run.run_id}/{stage.id}/{slot_id}/{ordinal}"))
            brief = (
                stage.slot_briefs[slot_index - 1] if slot_index <= len(stage.slot_briefs) else ""
            )
            instructions = "\n\n".join(
                item for item in (profile.objective, brief, run.spec.task) if item
            )
            spec = AgentRunSpec(
                run_id=run.run_id,
                attempt_id=attempt_id,
                stage_id=stage.id,
                parent_attempt_id=parent.spec.attempt_id if parent else None,
                profile_id=profile.id,
                profile_version=profile.version,
                instructions=instructions,
                input_manifest=inputs,
                backend=profile.backend,
                model_id=profile.model_id,
                effort=profile.effort,
                permissions=profile.permissions,
                skills=profile.skills,
                tools=profile.tools,
                workspace_revision=workspace_revision,
                run_snapshot_hash=run.spec.snapshot_hash,
            )
            action_id = uuid4()
            action_key = f"launch:{attempt_id}"
            preparation_id = str(action_id)
            lifecycle_owner_id = (
                derive_lifecycle_owner_id(preparation_id)
                if self._requires_backend_preflight_record()
                else None
            )
            preparation_event = (
                BackendPreparationIntentRecordedEvent(
                    event_id=uuid4(),
                    run_id=run.run_id,
                    occurred_at=self._now(),
                    actor=self.actor,
                    kind=EventKind.BACKEND_PREPARATION_INTENT_RECORDED,
                    action_id=action_id,
                    attempt_id=attempt_id,
                    preparation_id=preparation_id,
                    lifecycle_owner_id=lifecycle_owner_id,
                    attempt_spec_hash=content_hash(canonical_json(spec)),
                )
                if lifecycle_owner_id is not None
                else None
            )
            active_stages = sorted(
                {
                    *run.state.active_stages,
                    stage.id,
                }
            )
            reservations = self._reservation_creations(run, stage, attempt_id)
            mutation = LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=RunStatus.RUNNING,
                    active_stages=tuple(active_stages),
                    attempts_used=run.state.attempts_used + 1,
                    elapsed_seconds=self._elapsed(run),
                ),
                stage_updates=(StageUpdate(stage_id=stage.id, status=StageStatus.RUNNING),),
                attempt_creations=(
                    AttemptRegistration(
                        spec=spec,
                        stage_id=stage.id,
                        slot_id=slot_id,
                        state=AttemptState(
                            attempt_id=attempt_id,
                            status=AttemptStatus.LAUNCHING,
                            effective_input_revision=content_hash(canonical_json(inputs)),
                            worker_lifecycle_owner_id=lifecycle_owner_id,
                        ),
                    ),
                ),
                outbox_actions=(
                    OutboxIntent(
                        action_id=action_id,
                        action_key=action_key,
                        kind="launch_attempt",
                        payload={
                            "attempt_id": attempt_id,
                            "stage_id": stage.id,
                            "slot_id": slot_id,
                        },
                    ),
                ),
                events=(preparation_event,) if preparation_event is not None else (),
                reservations=reservations,
            )
            receipt = self.ledger.apply(mutation)
            if receipt.outcome != CommandOutcome.ACCEPTED:
                if receipt.reason and receipt.reason.startswith("stale_revision"):
                    return False
                raise LedgerInvariantError(receipt.reason or "attempt admission was rejected")
            return True
        return False

    def _retry_allowed(
        self,
        run: PersistedRun,
        stage: ResolvedStage,
        profile_id: str,
        lineage: Sequence[PersistedAttempt],
    ) -> bool:
        previous = lineage[-1]
        policy = self._profile(run, profile_id).retry_policy
        return (
            run.spec.workflow.policy.allow_retry
            and previous.state.status
            in {AttemptStatus.FAILED, AttemptStatus.TIMED_OUT, AttemptStatus.CANCELLED}
            and previous.state.error_class in policy.recoverable_classes
            and len(lineage) < min(policy.max_attempts, run.spec.workflow.max_attempts_per_slot)
            and (not policy.require_safe_retry or previous.state.safe_to_retry)
            and (
                previous.state.status != AttemptStatus.CANCELLED or previous.state.retry_authorized
            )
        )

    def _stage_has_only_settled_slots(self, run: PersistedRun, stage: ResolvedStage) -> bool:
        slots = resolve_stage_slots(run, stage)
        attempts = self.ledger.list_attempts(run.run_id, stage.id)
        for slot_id, profile_id in slots:
            lineage = self._ordered_lineage([item for item in attempts if item.slot_id == slot_id])
            if not lineage:
                return False
            latest = lineage[-1]
            if latest.state.status in _ACTIVE_ATTEMPT_STATES:
                return False
            if latest.state.status != AttemptStatus.SUCCEEDED and self._retry_allowed(
                run, stage, profile_id, lineage
            ):
                return False
            if latest.state.status != AttemptStatus.SUCCEEDED:
                return False
            if latest.result is None or latest.result.result is None:
                return False
        return True

    @staticmethod
    def _ordered_lineage(attempts: Sequence[PersistedAttempt]) -> list[PersistedAttempt]:
        """Order retries by their explicit parent link, independent of timestamps."""
        if not attempts:
            return []
        by_id = {item.spec.attempt_id: item for item in attempts}
        roots = [item for item in attempts if item.spec.parent_attempt_id is None]
        if len(roots) != 1:
            raise LedgerInvariantError("slot attempt lineage must have exactly one root")
        ordered = [roots[0]]
        while len(ordered) < len(attempts):
            children = [
                item
                for item in attempts
                if item.spec.parent_attempt_id == ordered[-1].spec.attempt_id
            ]
            if len(children) != 1:
                raise LedgerInvariantError("slot attempt lineage must have a single retry child")
            ordered.append(children[0])
        if len({item.spec.attempt_id for item in ordered}) != len(by_id):
            raise LedgerInvariantError("slot attempt lineage contains a disconnected attempt")
        return ordered

    def _complete_worker_stage(self, run: PersistedRun, stage: ResolvedStage) -> None:
        slots = resolve_stage_slots(run, stage)
        attempts = self.ledger.list_attempts(run.run_id, stage.id)
        results: list[WorkerResult] = []
        for slot_id, _profile_id in slots:
            lineage = self._ordered_lineage([item for item in attempts if item.slot_id == slot_id])
            terminal = lineage[-1]
            if terminal.result is None or terminal.result.result is None:
                raise LedgerInvariantError(f"successful slot {slot_id} has no normalized result")
            results.append(terminal.result.result)
        outputs = tuple(artifact for result in results for artifact in result.artifacts)
        if any(result.status == OutputStatus.BLOCKED for result in results):
            result_status = OutputStatus.BLOCKED
        elif any(result.status == OutputStatus.FAIL for result in results):
            result_status = OutputStatus.FAIL
        else:
            result_status = OutputStatus.PASS
        revisions = tuple(
            dict.fromkeys(
                result.workspace_revision for result in results if result.workspace_revision
            )
        )
        workspace_revision = revisions[0] if len(revisions) == 1 else None
        passed = result_status == OutputStatus.PASS
        completion_passes = result_status != OutputStatus.BLOCKED and (
            (
                stage.completion in {StageCompletion.ARTIFACT_READY, StageCompletion.REPORT_PASSED}
                and passed
            )
            or stage.completion == StageCompletion.REPORT_PRESENT
        )
        if result_status == OutputStatus.BLOCKED:
            status = StageStatus.BLOCKED
        else:
            status = StageStatus.SUCCEEDED if completion_passes else StageStatus.FAILED
        self._update_stage(
            run,
            StageUpdate(
                stage_id=stage.id,
                status=status,
                result=StageResult(
                    outputs=outputs,
                    result_status=result_status,
                    workspace_revision=workspace_revision,
                ),
            ),
            status=RunStatus.RUNNING,
            reason=(
                f"stage {stage.id} reported blocked"
                if result_status == OutputStatus.BLOCKED
                else None
                if completion_passes
                else f"stage {stage.id} did not meet {stage.completion.value}"
            ),
        )

    def _complete_integration_stage(
        self, run: PersistedRun, stage: ResolvedStage, repair_decision: str | None
    ) -> None:
        inputs, input_workspace_revision = resolve_stage_inputs(
            run, stage, repair_decision=repair_decision
        )
        revision = (
            input_workspace_revision
            if stage.kind == StageKind.INTEGRATION_CHECK and input_workspace_revision is not None
            else content_hash(
                canonical_json(
                    {
                        "run_snapshot": run.spec.snapshot_hash,
                        "stage": stage.id,
                        "inputs": inputs,
                    }
                )
            )
        )
        output_name = stage.required_outputs[0] if stage.required_outputs else "revision"
        result = StageResult(
            outputs=(
                ArtifactEntry(
                    name=output_name,
                    schema_id="revision-v1",
                    content_hash=revision,
                ),
            ),
            result_status=OutputStatus.PASS,
            workspace_revision=revision,
        )
        self._update_stage(
            run,
            StageUpdate(stage_id=stage.id, status=StageStatus.SUCCEEDED, result=result),
            status=RunStatus.RUNNING,
        )

    def _complete_repair_gate(self, run: PersistedRun, stage: ResolvedStage) -> None:
        projections = {item.stage_id: item for item in run.stages}
        statuses = []
        for stage_id in ("review", "test"):
            projection = projections.get(stage_id)
            result = projection.result if projection is not None else None
            if result is None or result.result_status is None:
                self._update_stage(
                    run,
                    StageUpdate(stage_id=stage.id, status=StageStatus.BLOCKED),
                    status=RunStatus.ATTENTION_REQUIRED,
                    reason=f"repair gate lacks {stage_id} report evidence",
                )
                return
            statuses.append(result.result_status)
        decision: Literal["repair_needed", "repair_not_needed"] = (
            "repair_needed" if OutputStatus.FAIL in statuses else "repair_not_needed"
        )
        result = StageResult(decision=decision, result_status=OutputStatus.PASS)
        self._update_stage(
            run,
            StageUpdate(stage_id=stage.id, status=StageStatus.SUCCEEDED, result=result),
            status=RunStatus.RUNNING,
        )

    def _complete_run(self, run: PersistedRun) -> None:
        try:
            for required in run.spec.workflow.required_outputs:
                stage_id, separator, output_name = required.partition(".")
                projection = next((item for item in run.stages if item.stage_id == stage_id), None)
                if not separator or projection is None or projection.result is None:
                    raise InputResolutionError(f"workflow output {required} is missing")
                if not any(item.name == output_name for item in projection.result.outputs):
                    raise InputResolutionError(f"workflow output {required} is missing")
            if run.spec.workflow.completion.value == "verified_revision":
                self._validate_verified_revision(run)
            if run.spec.workflow.completion.value == "verified_research":
                verify = next(item for item in run.stages if item.stage_id == "verify")
                if verify.result is None or verify.result.result_status != OutputStatus.PASS:
                    raise InputResolutionError("research verification report must pass")
        except (InputResolutionError, StopIteration) as error:
            self._set_run_status(
                run, RunStatus.ATTENTION_REQUIRED, f"workflow completion is unresolved: {error}"
            )
            return
        self._set_run_status(run, RunStatus.SUCCEEDED, "workflow completion rule satisfied")

    def _validate_verified_revision(self, run: PersistedRun) -> None:
        stages = {item.stage_id: item for item in run.stages}
        gate = stages.get("repair_gate")
        decision = gate.result.decision if gate and gate.result else None
        if decision is not None:
            branch_outputs = {
                branch: dict(outputs) for branch, outputs in run.spec.workflow.branch_outputs
            }.get(decision, {})
            revision_source = branch_outputs.get("revision")
            if revision_source is None:
                raise InputResolutionError("repair decision has no declared revision output")
            revision_stage_id, _, revision_name = revision_source.partition(".")
            revision_stage = stages.get(revision_stage_id)
            if revision_stage is None or revision_stage.result is None:
                raise InputResolutionError(f"selected revision {revision_source} is missing")
            if not any(item.name == revision_name for item in revision_stage.result.outputs):
                raise InputResolutionError(f"selected revision {revision_source} is missing")
            current_revision = revision_stage.result.workspace_revision
            for role in ("review", "test"):
                source = branch_outputs.get(role)
                if source is None:
                    raise InputResolutionError(f"repair decision has no declared {role} output")
                stage_id, _, output_name = source.partition(".")
                projection = stages.get(stage_id)
                if projection is None or projection.result is None:
                    raise InputResolutionError(f"selected verification {source} is missing")
                if projection.result.result_status != OutputStatus.PASS:
                    raise InputResolutionError(f"selected verification {source} did not pass")
                if not any(item.name == output_name for item in projection.result.outputs):
                    raise InputResolutionError(f"selected output {source} is missing")
                if projection.result.workspace_revision != current_revision:
                    raise InputResolutionError(f"verification {source} is for a stale revision")
            return

        revision_stage_id = "integration_check" if "integration_check" in stages else "integrate"
        revision_stage = stages.get(revision_stage_id)
        if revision_stage is None or revision_stage.result is None:
            raise InputResolutionError("verified workflow has no integrated revision")
        if not revision_stage.result.workspace_revision:
            raise InputResolutionError("integrated revision has no workspace identity")
        for stage_id in ("test", "review"):
            projection = stages.get(stage_id)
            if projection is None or projection.result is None:
                raise InputResolutionError(f"{stage_id} report is missing")
            if projection.result.result_status != OutputStatus.PASS:
                raise InputResolutionError(f"{stage_id} must pass before verified handoff")
            if projection.result.workspace_revision != revision_stage.result.workspace_revision:
                raise InputResolutionError(f"{stage_id} report is for a stale workspace revision")

    def _reservation_creations(
        self, run: PersistedRun, stage: ResolvedStage, attempt_id: str
    ) -> tuple[ReservationChange, ...]:
        capacities = (
            ("global", "all", self.global_parallelism),
            (
                "project",
                run.project_config.id,
                min(self.global_parallelism, run.project_config.max_parallelism),
            ),
            (
                "run",
                run.run_id,
                min(self.global_parallelism, run.spec.workflow.max_parallelism),
            ),
            ("stage", f"{run.run_id}/{stage.id}", len(resolve_stage_slots(run, stage))),
        )
        return tuple(
            ReservationChange(
                operation=ReservationOperation.RESERVE,
                reservation_id=f"{attempt_id}:{scope}",
                reservation_key=f"{attempt_id}:{scope}",
                attempt_id=attempt_id,
                scope=scope,
                resource_key=resource,
                capacity_limit=capacity,
            )
            for scope, resource, capacity in capacities
        )

    def _reservation_releases(self, run_id: str, attempt_id: str) -> tuple[ReservationChange, ...]:
        return tuple(
            ReservationChange(
                operation=ReservationOperation.RELEASE,
                reservation_id=item.reservation_id,
                reservation_key=item.reservation_key,
                attempt_id=attempt_id,
            )
            for item in self.ledger.list_reservations(run_id)
            if item.attempt_id == attempt_id and item.status.value == "held"
        )

    def _update_stage(
        self,
        run: PersistedRun,
        update: StageUpdate,
        *,
        status: RunStatus | None = None,
        reason: str | None = None,
    ) -> None:
        def build(current: PersistedRun) -> LedgerMutation:
            active = [
                item.stage_id
                for item in current.stages
                if item.stage_id != update.stage_id
                and item.status in {StageStatus.READY, StageStatus.RUNNING}
            ]
            if update.status in {StageStatus.READY, StageStatus.RUNNING}:
                active.append(update.stage_id)
            previous = next(
                item.status for item in current.stages if item.stage_id == update.stage_id
            )
            events: list[Event] = []
            if previous != update.status:
                events.append(
                    StageStatusChangedEvent(
                        event_id=uuid4(),
                        run_id=current.run_id,
                        occurred_at=self._now(),
                        actor=self.actor,
                        kind=EventKind.STAGE_STATUS_CHANGED,
                        stage_id=update.stage_id,
                        previous=previous,
                        current=update.status,
                        reason=reason,
                    )
                )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=current.run_id,
                expected_revision=current.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=status or current.state.status,
                    active_stages=tuple(sorted(active)),
                    elapsed_seconds=self._elapsed(current),
                    attention_reason=(reason if status == RunStatus.ATTENTION_REQUIRED else None),
                    resume_status=(
                        current.state.resume_status or current.state.status
                        if status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                stage_updates=(update,),
                events=tuple(events),
            )

        self._commit(run.run_id, build)

    def _set_run_status(self, run: PersistedRun, status: RunStatus, reason: str) -> None:
        def build(current: PersistedRun) -> LedgerMutation:
            events: list[Event] = []
            if current.state.status != status:
                events.append(
                    RunStatusChangedEvent(
                        event_id=uuid4(),
                        run_id=current.run_id,
                        occurred_at=self._now(),
                        actor=self.actor,
                        kind=EventKind.RUN_STATUS_CHANGED,
                        previous=current.state.status,
                        current=status,
                        reason=reason,
                    )
                )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=current.run_id,
                expected_revision=current.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=status,
                    active_stages=tuple(
                        item.stage_id
                        for item in current.stages
                        if item.status in {StageStatus.READY, StageStatus.RUNNING}
                    ),
                    elapsed_seconds=self._elapsed(current),
                    attention_reason=(reason if status == RunStatus.ATTENTION_REQUIRED else None),
                    resume_status=(
                        current.state.resume_status or current.state.status
                        if status == RunStatus.ATTENTION_REQUIRED
                        else None
                    ),
                ),
                events=tuple(events),
            )

        self._commit(run.run_id, build)

    def _run_has_owned_attempt(self, run_id: str) -> bool:
        return any(
            item.state.status in _ACTIVE_ATTEMPT_STATES
            for item in self.ledger.list_attempts(run_id)
        )

    def _status_after_settlement(self, run: PersistedRun, attempt_id: str) -> RunStatus:
        remaining = any(
            item.spec.attempt_id != attempt_id and item.state.status in _ACTIVE_ATTEMPT_STATES
            for item in self.ledger.list_attempts(run.run_id)
        )
        if run.state.status == RunStatus.STOPPING:
            return RunStatus.STOPPING if remaining else RunStatus.STOPPED
        if run.state.status == RunStatus.PAUSE_REQUESTED:
            return RunStatus.PAUSE_REQUESTED if remaining else RunStatus.PAUSED
        if run.state.status == RunStatus.ATTENTION_REQUIRED:
            if run.state.resume_status == RunStatus.STOPPING and not remaining:
                return RunStatus.STOPPING
            if (
                run.state.resume_status in {RunStatus.PAUSE_REQUESTED, RunStatus.PAUSED}
                and not remaining
            ):
                return RunStatus.PAUSED
            return RunStatus.ATTENTION_REQUIRED
        return RunStatus.RUNNING

    def _status_after_reconciliation(
        self, run: PersistedRun, attempt_id: str, settled_status: AttemptStatus
    ) -> RunStatus:
        if any(
            item.spec.attempt_id != attempt_id and item.state.status in _ACTIVE_ATTEMPT_STATES
            for item in self.ledger.list_attempts(run.run_id)
        ):
            return RunStatus.ATTENTION_REQUIRED
        if any(item.status == StageStatus.BLOCKED for item in run.stages):
            return RunStatus.ATTENTION_REQUIRED

        selected_stop_is_unresolved = settled_status == AttemptStatus.CANCELLED and any(
            record.kind == InterventionKind.STOP_ATTEMPT
            and record.target_id == attempt_id
            and record.payload.get("reason") != "timeout"
            for record in self.ledger.list_intervention_records(run.run_id)
        )
        if selected_stop_is_unresolved:
            return RunStatus.ATTENTION_REQUIRED

        reason = run.state.attention_reason or ""
        may_clear_attention = (
            reason.startswith("reconciliation pending:")
            or "control delivery outcome is unresolved" in reason
            or "worker ownership remains unresolved" in reason
            or "backend control acknowledgement identity is uncertain" in reason
            or (
                "selected attempt stop requested" in reason
                and settled_status != AttemptStatus.CANCELLED
            )
        )
        if run.state.status != RunStatus.ATTENTION_REQUIRED or not may_clear_attention:
            return run.state.status

        resume_status = run.state.resume_status or RunStatus.RUNNING
        if resume_status in {RunStatus.PAUSE_REQUESTED, RunStatus.PAUSED}:
            return RunStatus.PAUSED
        if resume_status in {RunStatus.STOPPING, RunStatus.STOPPED}:
            return RunStatus.STOPPED
        return RunStatus.RUNNING

    def _expire_run(self, run: PersistedRun) -> None:
        active = any(
            attempt.state.status in _ACTIVE_ATTEMPT_STATES
            for attempt in self.ledger.list_attempts(run.run_id)
        )
        self._set_run_status(
            run,
            RunStatus.ATTENTION_REQUIRED if active else RunStatus.FAILED,
            "workflow duration budget is exhausted",
        )

    def _commit(self, run_id: str, build: Callable[[PersistedRun], LedgerMutation]) -> None:
        for _ in range(5):
            run = self.ledger.get_run(run_id)
            mutation = build(run)
            receipt = self.ledger.apply(mutation)
            if receipt.outcome == CommandOutcome.ACCEPTED:
                return
            if receipt.reason and receipt.reason.startswith("stale_revision"):
                continue
            raise LedgerInvariantError(receipt.reason or "ledger mutation was rejected")
        raise LedgerInvariantError(f"run {run_id} kept changing during coordinator mutation")

    def _remember_elapsed_origin(self, run: PersistedRun) -> None:
        if run.run_id not in self._elapsed_origins:
            self._elapsed_origins[run.run_id] = (
                self.clock.now,
                run.state.elapsed_seconds,
            )

    def _elapsed(self, run: PersistedRun) -> float:
        self._remember_elapsed_origin(run)
        clock_origin, elapsed_origin = self._elapsed_origins[run.run_id]
        return max(run.state.elapsed_seconds, elapsed_origin + self.clock.now - clock_origin)

    def _now(self) -> datetime:
        return self.clock.utc_now

    def _profile(self, run: PersistedRun, profile_id: str) -> ResolvedProfile:
        profile = next((item for item in run.spec.profiles if item.id == profile_id), None)
        if profile is None:
            raise LedgerInvariantError(f"resolved run has no profile {profile_id}")
        if profile.backend not in run.spec.workflow.policy.allowed_backends:
            raise LedgerInvariantError(f"profile {profile_id} backend is forbidden by policy")
        if profile.model_binding not in run.spec.workflow.policy.allowed_model_bindings:
            raise LedgerInvariantError(f"profile {profile_id} model binding is forbidden by policy")
        if profile_id not in run.spec.workflow.allowed_profiles:
            raise LedgerInvariantError(f"profile {profile_id} is forbidden by workflow")
        return profile

    @staticmethod
    def _stage(run: PersistedRun, stage_id: str) -> ResolvedStage:
        stage = next((item for item in run.spec.workflow.stages if item.id == stage_id), None)
        if stage is None:
            raise LedgerInvariantError(f"run snapshot has no stage {stage_id}")
        return stage

    def _action_for_attempt(self, attempt_id: str) -> UUID:
        action = next(
            (
                item
                for item in self.ledger.list_outbox_actions()
                if item.kind == "launch_attempt" and item.payload.get("attempt_id") == attempt_id
            ),
            None,
        )
        if action is None:
            raise LedgerInvariantError(f"attempt {attempt_id} has no durable launch action")
        return action.action_id

    def _worker_done(self, attempt_id: str, _task: asyncio.Task[None]) -> None:
        self._workers.pop(attempt_id, None)

    async def _join_finished_workers(self) -> None:
        tasks = tuple(self._workers.values())
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
