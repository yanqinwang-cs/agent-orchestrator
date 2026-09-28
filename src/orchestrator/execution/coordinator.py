"""Bounded execution for immutable workflow snapshots and normalized workers."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from functools import partial
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from pydantic import ValidationError

from orchestrator.backends.fake import FakeBackendFailure, FakeClock
from orchestrator.backends.protocol import WorkerBackend
from orchestrator.domain.backend import (
    ArtifactEntry,
    OutputStatus,
    WorkerDisconnectedEvent,
    WorkerEvent,
    WorkerFailureEvent,
    WorkerHandle,
    WorkerProgressEvent,
    WorkerResult,
    WorkerStartedEvent,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    AttemptState,
    AttemptStatus,
    Condition,
    Event,
    EventKind,
    FailureClass,
    InputEntry,
    OutboxStatus,
    ResolvedProfile,
    ResolvedStage,
    RunStatus,
    RunStatusChangedEvent,
    SlotKind,
    StageCompletion,
    StageKind,
    StageStatus,
    StageStatusChangedEvent,
)
from orchestrator.persistence.ledger import (
    LedgerInvariantError,
    ReservationConflict,
    SQLiteLedger,
    canonical_json,
    content_hash,
)
from orchestrator.persistence.models import (
    AttemptRegistration,
    AttemptResultRegistration,
    CommandOutcome,
    LedgerMutation,
    OutboxAction,
    OutboxIntent,
    OutboxOutcomeChange,
    PersistedAttempt,
    PersistedRun,
    ReservationChange,
    ReservationOperation,
    RunProjectionUpdate,
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


class InputResolutionError(ValueError):
    """A declared stage input is absent from the persisted run evidence."""


def resolve_stage_slots(run: PersistedRun, stage: ResolvedStage) -> tuple[tuple[str, str], ...]:
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
    result: list[tuple[str, str]] = []
    for index, profile_id in enumerate(selection.profile_ids, start=1):
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
    ) -> None:
        if global_parallelism < 1:
            raise ValueError("global_parallelism must be positive")
        if ownership.lease is None:
            raise ValueError("coordinator ownership must be acquired before execution")
        self.ledger = ledger
        self.backend = backend
        self.ownership = ownership
        self.clock = clock or FakeClock(origin=datetime.now(UTC))
        self.global_parallelism = global_parallelism
        self.actor = actor
        self._elapsed_origins: dict[str, tuple[float, float]] = {}
        self._workers: dict[str, asyncio.Task[None]] = {}

    def advance(self, run_id: str) -> bool:
        """Persist deterministic stage transitions and launch intents until quiescent."""
        changed_any = False
        for _ in range(10_000):
            run = self.ledger.get_run(run_id)
            if run.state.status in _TERMINAL_RUN_STATES:
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
        attempt_id = str(action.payload.get("attempt_id", ""))
        attempt = self.ledger.get_attempt(attempt_id)
        try:
            preflight = await self.backend.preflight(attempt.spec)
            if not preflight.accepted:
                issue = "; ".join(item.message for item in preflight.issues) or "preflight rejected"
                self._settle_launch_failure(
                    action.action_id,
                    attempt,
                    FailureClass.CONFIGURATION,
                    issue,
                    safe_to_retry=False,
                )
                return 0
            handle = await self.backend.start(attempt.spec)
        except FakeBackendFailure as error:
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
                f"launch outcome is unknown: {type(error).__name__}: {error}",
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
                f"launch acknowledgement could not be persisted: {error}",
            )
            return 0
        task = asyncio.create_task(self._consume(attempt_id, handle))
        self._workers[attempt_id] = task
        task.add_done_callback(partial(self._worker_done, attempt_id))
        return 1

    async def run_until_stalled(self, run_id: str, *, max_steps: int = 10_000) -> RunStatus:
        """Drive internal transitions and fake workers until completion or a genuine stall."""
        if not self._workers:
            self.mark_claimed_launches_unknown(run_id)
        for _ in range(max_steps):
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

    async def wait_for_workers(self) -> None:
        """Wait for every worker event stream currently owned by this coordinator."""
        tasks = tuple(self._workers.values())
        if tasks:
            await asyncio.gather(*tasks)

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
                    await self.backend.interrupt(handle, uuid4())
                    receipt = await self.backend.close(handle)
                    safe = receipt.settled
                    self._settle_failure(
                        attempt_id,
                        AttemptStatus.TIMED_OUT if safe else AttemptStatus.OUTCOME_UNKNOWN,
                        FailureClass.TIMEOUT,
                        "worker exceeded its profile timeout",
                        safe_to_retry=safe,
                        run_status=(None if safe else RunStatus.ATTENTION_REQUIRED),
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
                f"worker stream outcome is unknown: {type(error).__name__}: {error}",
            )

    @staticmethod
    def _validate_event_order(event: WorkerEvent, attempt_id: str, previous: int) -> int:
        if event.attempt_id != attempt_id:
            raise ValueError("worker event belongs to another attempt")
        if event.sequence <= previous:
            raise ValueError("worker event sequence is not strictly increasing")
        return event.sequence

    def _settle_terminal(self, attempt_id: str, event: WorkerTerminalEvent) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        run = self.ledger.get_run(attempt.spec.run_id)
        stage = self._stage(run, attempt.stage_id)
        result: WorkerResult | None = None
        validation_error: str | None = None
        try:
            result = WorkerResult.model_validate(event.result.model_dump(mode="json"))
            if event.attempt_id != attempt_id or result.attempt_id != attempt_id:
                raise ValueError("terminal result attempt identity does not match launch")
            expected_input = content_hash(canonical_json(attempt.spec.input_manifest))
            if result.input_revision != expected_input:
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
        except (ValidationError, ValueError) as error:
            validation_error = f"invalid artifact-envelope-v1 result: {error}"

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
            )
            return

        assert result is not None
        self._settle_success(attempt_id, result)

    def _settle_success(self, attempt_id: str, result: WorkerResult) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
        reservations = self._reservation_releases(attempt.spec.run_id, attempt_id)

        def build(run: PersistedRun) -> LedgerMutation:
            latest_attempt = self.ledger.get_attempt(attempt_id)
            finished = self._now()
            state = latest_attempt.state.model_copy(
                update={
                    "status": AttemptStatus.SUCCEEDED,
                    "finished_at": finished,
                    "receipt_id": f"worker:{attempt_id}",
                }
            )
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=finished,
                run_update=RunProjectionUpdate(
                    status=RunStatus.RUNNING,
                    elapsed_seconds=self._elapsed(run),
                ),
                attempt_updates=(state,),
                attempt_results=(AttemptResultRegistration(attempt_id=attempt_id, result=result),),
                reservations=reservations,
            )

        self._commit(attempt.spec.run_id, build)

    def _settle_worker_failure(self, attempt_id: str, event: WorkerFailureEvent) -> None:
        self._settle_failure(
            attempt_id,
            AttemptStatus.FAILED,
            event.failure_class,
            event.summary,
            safe_to_retry=event.safe_to_retry,
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
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=RunStatus.RUNNING,
                    elapsed_seconds=self._elapsed(run),
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
    ) -> None:
        attempt = self.ledger.get_attempt(attempt_id)
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
            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=self._now(),
                run_update=RunProjectionUpdate(
                    status=run_status or RunStatus.RUNNING,
                    elapsed_seconds=self._elapsed(run),
                ),
                attempt_updates=(failed,),
                attempt_results=(result_registration,) if result_registration else (),
                reservations=releases,
            )

        self._commit(attempt.spec.run_id, build)

    def _mark_unknown_launch(
        self, action_id: UUID, attempt: PersistedAttempt, summary: str
    ) -> None:
        if attempt.state.status == AttemptStatus.OUTCOME_UNKNOWN:
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
                }
            )

            return LedgerMutation(
                command_id=uuid4(),
                run_id=run.run_id,
                expected_revision=run.state.revision,
                actor=self.actor,
                occurred_at=started,
                run_update=RunProjectionUpdate(
                    status=RunStatus.RUNNING,
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
        slots = resolve_stage_slots(run, stage)
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
                        state=AttemptState(attempt_id=attempt_id, status=AttemptStatus.LAUNCHING),
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
            and previous.state.status in {AttemptStatus.FAILED, AttemptStatus.TIMED_OUT}
            and previous.state.error_class in policy.recoverable_classes
            and len(lineage) < min(policy.max_attempts, run.spec.workflow.max_attempts_per_slot)
            and (not policy.require_safe_retry or previous.state.safe_to_retry)
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
                ),
                events=tuple(events),
            )

        self._commit(run.run_id, build)

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
