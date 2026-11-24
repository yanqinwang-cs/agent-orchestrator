"""Versioned records and commands for the durable runtime ledger."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from orchestrator.domain.backend import (
    ArtifactEntry,
    BackendPreflightSnapshot,
    OutputStatus,
    WorkerResult,
)
from orchestrator.domain.decisions import (
    DecisionDisposition,
    DecisionEngineFailure,
    DecisionRequest,
    DecisionResult,
    decision_request_hash,
    decision_result_hash,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    Artifact,
    AttemptState,
    BackendPreflightRecordedEvent,
    Event,
    FrozenModel,
    Handoff,
    Identifier,
    Intervention,
    InterventionKind,
    InterventionTargetScope,
    NonEmpty,
    OutboxStatus,
    ProjectConfig,
    ReservationStatus,
    RunSpec,
    RunState,
    RunStatus,
    StageStatus,
)


class StageResult(FrozenModel):
    schema_version: Literal[1] = 1
    outputs: tuple[ArtifactEntry, ...] = ()
    result_status: OutputStatus | None = None
    workspace_revision: str | None = None
    decision: Literal["repair_needed", "repair_not_needed"] | None = None


class StageUpdate(FrozenModel):
    stage_id: Identifier
    status: StageStatus
    result: StageResult | None = None


class StageProjection(FrozenModel):
    schema_version: Literal[1] = 1
    stage_id: Identifier
    status: StageStatus
    updated_at: datetime
    result: StageResult | None = None


class RunProjectionUpdate(FrozenModel):
    status: RunStatus | None = None
    active_stages: tuple[Identifier, ...] | None = None
    attempts_used: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0)
    attention_reason: str | None = None
    resume_status: RunStatus | None = None


class AttemptRegistration(FrozenModel):
    spec: AgentRunSpec
    stage_id: Identifier
    slot_id: NonEmpty
    state: AttemptState

    @model_validator(mode="after")
    def check_identity(self) -> AttemptRegistration:
        if self.spec.attempt_id != self.state.attempt_id:
            raise ValueError("attempt specification and state IDs must match")
        return self


class AttemptResultRegistration(FrozenModel):
    attempt_id: NonEmpty
    result: WorkerResult | None = None
    validation_error: NonEmpty | None = None

    @model_validator(mode="after")
    def check_result_shape(self) -> AttemptResultRegistration:
        if (self.result is None) == (self.validation_error is None):
            raise ValueError("provide either a validated result or a validation error")
        if self.result is not None and self.result.attempt_id != self.attempt_id:
            raise ValueError("worker result and attempt IDs must match")
        return self


class AttemptResult(FrozenModel):
    schema_version: Literal[1] = 1
    result: WorkerResult | None = None
    result_hash: NonEmpty
    validation_error: str | None = None
    recorded_at: datetime

    @model_validator(mode="after")
    def check_result_shape(self) -> AttemptResult:
        if (self.result is None) == (self.validation_error is None):
            raise ValueError("persisted result must be valid or carry a validation error")
        return self


class OutboxIntent(FrozenModel):
    action_id: UUID
    action_key: NonEmpty
    kind: NonEmpty
    payload: dict[str, Any]


class OutboxOutcomeChange(FrozenModel):
    action_id: UUID
    status: OutboxStatus
    result: str | None = None

    @model_validator(mode="after")
    def require_terminal_outcome(self) -> OutboxOutcomeChange:
        if self.status not in (
            OutboxStatus.ACKNOWLEDGED,
            OutboxStatus.REJECTED,
            OutboxStatus.UNKNOWN,
        ):
            raise ValueError("outbox outcome must be acknowledged, rejected, or unknown")
        return self


class OutboxAction(FrozenModel):
    schema_version: Literal[1] = 1
    action_id: UUID
    action_key: NonEmpty
    run_id: NonEmpty
    command_id: UUID
    kind: NonEmpty
    payload: dict[str, Any]
    status: OutboxStatus
    created_at: datetime
    claimed_at: datetime | None = None
    claimed_by: str | None = None
    outcome_command_id: UUID | None = None
    result: str | None = None


class ReservationOperation(StrEnum):
    RESERVE = "reserve"
    RELEASE = "release"


class ReservationChange(FrozenModel):
    operation: ReservationOperation
    reservation_id: NonEmpty
    reservation_key: NonEmpty
    attempt_id: NonEmpty | None = None
    scope: NonEmpty | None = None
    resource_key: NonEmpty | None = None
    capacity_limit: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def check_reservation_shape(self) -> ReservationChange:
        if self.operation == ReservationOperation.RESERVE and (
            self.scope is None or self.resource_key is None
        ):
            raise ValueError("reserving requires scope and resource_key")
        return self


class ReservationRecord(FrozenModel):
    schema_version: Literal[1] = 1
    reservation_id: NonEmpty
    reservation_key: NonEmpty
    run_id: NonEmpty
    attempt_id: NonEmpty | None = None
    scope: NonEmpty
    resource_key: NonEmpty
    status: ReservationStatus
    created_at: datetime
    released_at: datetime | None = None


class ArtifactPublication(FrozenModel):
    command_id: UUID
    expected_run_revision: int = Field(ge=0)
    actor: NonEmpty
    run_id: NonEmpty
    attempt_id: NonEmpty
    artifact_id: NonEmpty
    input_revision: NonEmpty
    workspace_revision: str | None = None
    schema_id: Identifier
    occurred_at: datetime


class ArtifactRegistration(FrozenModel):
    artifact: Artifact
    size_bytes: int = Field(ge=0)


class ArtifactManifest(FrozenModel):
    schema_version: Literal[1] = 1
    artifact: Artifact
    size_bytes: int = Field(ge=0)
    created_at: datetime


class ControlDeliveryStatus(StrEnum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    DELIVERING = "delivering"
    ACKNOWLEDGED = "acknowledged"
    REJECTED = "rejected"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"
    UNKNOWN = "unknown"


class ControlDelivery(FrozenModel):
    schema_version: Literal[1] = 1
    action_id: UUID
    attempt_id: NonEmpty
    status: ControlDeliveryStatus
    requested_at: datetime
    attempted_at: datetime | None = None
    completed_at: datetime | None = None
    detail: str | None = None
    effective_input_revision: str | None = None
    worker_handle_id: str | None = None
    worker_thread_id: str | None = None
    worker_turn_id: str | None = None


class InterventionRecord(FrozenModel):
    """Inspectable, versioned lifecycle state for one accepted or rejected command."""

    schema_version: Literal[1] = 1
    command_id: UUID
    run_id: NonEmpty
    actor: NonEmpty
    target_scope: InterventionTargetScope
    target_id: NonEmpty
    expected_run_revision: int = Field(ge=0)
    kind: InterventionKind
    payload: dict[str, Any]
    requested_at: datetime
    validation_outcome: Literal["accepted", "rejected"]
    validation_detail: str | None = None
    delivery_state: ControlDeliveryStatus | None = None
    deliveries: tuple[ControlDelivery, ...] = ()
    resulting_run_revision: int | None = Field(default=None, ge=0)
    resulting_attempt_revision: str | None = None

    @model_validator(mode="after")
    def require_delivery_state(self) -> InterventionRecord:
        if self.deliveries and self.delivery_state is None:
            raise ValueError("delivery state is required when a control delivery exists")
        if self.validation_outcome == "rejected" and self.deliveries:
            raise ValueError("rejected intervention cannot have control deliveries")
        return self

    @classmethod
    def from_request(
        cls,
        request: Intervention,
        *,
        run_id: str,
        target_scope: InterventionTargetScope,
        target_id: str,
        requested_at: datetime,
        validation_outcome: Literal["accepted", "rejected"],
        validation_detail: str | None = None,
        delivery_state: ControlDeliveryStatus | None = None,
        deliveries: tuple[ControlDelivery, ...] = (),
        resulting_run_revision: int | None = None,
        resulting_attempt_revision: str | None = None,
    ) -> InterventionRecord:
        return cls(
            command_id=request.command_id,
            run_id=run_id,
            actor=request.actor,
            target_scope=target_scope,
            target_id=target_id,
            expected_run_revision=request.expected_run_revision,
            kind=request.kind,
            payload=request.model_dump(mode="json"),
            requested_at=requested_at,
            validation_outcome=validation_outcome,
            validation_detail=validation_detail,
            delivery_state=delivery_state,
            deliveries=deliveries,
            resulting_run_revision=resulting_run_revision,
            resulting_attempt_revision=resulting_attempt_revision,
        )


class StageRedirect(FrozenModel):
    schema_version: Literal[1] = 1
    run_id: NonEmpty
    stage_id: Identifier
    recipient_profile_id: Identifier
    command_id: UUID
    updated_at: datetime


class BackendPreflightRecord(FrozenModel):
    """Immutable, hash-linked record of one attempt's effective preflight."""

    schema_version: Literal[1] = 1
    record_id: NonEmpty
    run_id: NonEmpty
    attempt_id: NonEmpty
    preparation_id: NonEmpty
    attempt_spec_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    accepted: bool
    occurred_at: datetime
    snapshot: BackendPreflightSnapshot
    record_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def require_linkage(self) -> BackendPreflightRecord:
        if self.snapshot.preparation_id != self.preparation_id:
            raise ValueError("preflight snapshot preparation ID does not match its record")
        return self


class DecisionRecord(FrozenModel):
    """Durable request and write-once normalized reply/disposition for a decision."""

    schema_version: Literal[1] = 1
    request: DecisionRequest
    request_hash: str
    request_persisted_revision: int = Field(ge=1)
    result: DecisionResult | None = None
    failure: DecisionEngineFailure | None = None
    disposition: DecisionDisposition | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_lifecycle_shape(self) -> DecisionRecord:
        if self.request_hash != decision_request_hash(self.request):
            raise ValueError("decision request hash does not match request")
        if self.request_persisted_revision != self.request.current_run_revision + 1:
            raise ValueError("decision request persistence revision must follow its run revision")
        complete = self.completed_at is not None
        if complete != (self.disposition is not None):
            raise ValueError("completed decision requires a disposition")
        if (self.result is not None) and (self.failure is not None):
            raise ValueError("decision record cannot contain both result and failure")
        if complete != (self.result is not None or self.failure is not None):
            raise ValueError("completed decision requires exactly one result or failure")
        if self.result is not None and self.result.decision_id != self.request.decision_id:
            raise ValueError("decision result identity does not match request")
        if self.failure is not None and self.failure.decision_id != self.request.decision_id:
            raise ValueError("decision failure identity does not match request")
        if self.disposition is not None:
            if self.disposition.decision_id != self.request.decision_id:
                raise ValueError("decision disposition identity does not match request")
            if self.disposition.request_hash != self.request_hash:
                raise ValueError("decision disposition references another request")
            expected_result_hash = decision_result_hash(self.result) if self.result else None
            if self.disposition.result_hash != expected_result_hash:
                raise ValueError("decision disposition result hash does not match reply")
        return self

    @property
    def decision_id(self) -> UUID:
        return self.request.decision_id

    @property
    def run_id(self) -> str:
        return self.request.run_id

    @property
    def question_id(self) -> str:
        return self.request.question_id


class CommandOutcome(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CommandReceipt(FrozenModel):
    schema_version: Literal[1] = 1
    command_id: UUID
    run_id: NonEmpty
    expected_revision: int | None = None
    outcome: CommandOutcome
    resulting_revision: int = Field(ge=0)
    event_sequences: tuple[int, ...] = ()
    reason: str | None = None
    created_at: datetime


class OwnerLease(FrozenModel):
    schema_version: Literal[1] = 1
    generation: int = Field(ge=1)
    owner_id: NonEmpty
    acquired_at: datetime


class LedgerMutation(FrozenModel):
    schema_version: Literal[1] = 1
    command_id: UUID
    run_id: NonEmpty
    expected_revision: int = Field(ge=0)
    actor: NonEmpty
    occurred_at: datetime
    run_update: RunProjectionUpdate | None = None
    stage_updates: tuple[StageUpdate, ...] = ()
    attempt_creations: tuple[AttemptRegistration, ...] = ()
    attempt_updates: tuple[AttemptState, ...] = ()
    attempt_results: tuple[AttemptResultRegistration, ...] = ()
    events: tuple[Event, ...] = ()
    outbox_actions: tuple[OutboxIntent, ...] = ()
    outbox_outcomes: tuple[OutboxOutcomeChange, ...] = ()
    reservations: tuple[ReservationChange, ...] = ()
    handoffs: tuple[Handoff, ...] = ()
    artifacts: tuple[ArtifactRegistration, ...] = ()
    intervention_records: tuple[InterventionRecord, ...] = ()
    stage_redirects: tuple[StageRedirect, ...] = ()
    decision_records: tuple[DecisionRecord, ...] = ()
    backend_preflight_records: tuple[BackendPreflightRecord, ...] = ()
    receipt_outcome: CommandOutcome = CommandOutcome.ACCEPTED
    receipt_reason: str | None = None

    @model_validator(mode="after")
    def reject_duplicate_targets(self) -> LedgerMutation:
        stage_ids = [stage.stage_id for stage in self.stage_updates]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("a mutation can update each stage only once")
        attempt_ids = [item.spec.attempt_id for item in self.attempt_creations]
        attempt_ids.extend(item.attempt_id for item in self.attempt_updates)
        result_attempt_ids = [item.attempt_id for item in self.attempt_results]
        if len(result_attempt_ids) != len(set(result_attempt_ids)):
            raise ValueError("a mutation can record each attempt result only once")
        if len(attempt_ids) != len(set(attempt_ids)):
            raise ValueError("a mutation can update each attempt only once")
        action_ids = [item.action_id for item in self.outbox_actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("a mutation can add each outbox action only once")
        outbox_outcome_ids = [item.action_id for item in self.outbox_outcomes]
        if len(outbox_outcome_ids) != len(set(outbox_outcome_ids)):
            raise ValueError("a mutation can update each outbox action only once")
        artifact_ids = [item.artifact.id for item in self.artifacts]
        if len(artifact_ids) != len(set(artifact_ids)):
            raise ValueError("a mutation can publish each artifact only once")
        intervention_ids = [item.command_id for item in self.intervention_records]
        if len(intervention_ids) != len(set(intervention_ids)):
            raise ValueError("a mutation can update each intervention only once")
        redirect_stages = [item.stage_id for item in self.stage_redirects]
        if len(redirect_stages) != len(set(redirect_stages)):
            raise ValueError("a mutation can update each stage redirect only once")
        decision_ids = [item.decision_id for item in self.decision_records]
        if len(decision_ids) != len(set(decision_ids)):
            raise ValueError("a mutation can update each decision record only once")
        preflight_ids = [item.record_id for item in self.backend_preflight_records]
        if len(preflight_ids) != len(set(preflight_ids)):
            raise ValueError("a mutation can add each backend preflight record only once")
        for record in self.backend_preflight_records:
            if not any(
                isinstance(event, BackendPreflightRecordedEvent)
                and event.record_id == record.record_id
                and event.attempt_id == record.attempt_id
                and event.record_hash == record.record_hash
                and event.accepted == record.accepted
                for event in self.events
            ):
                raise ValueError("backend preflight records require a matching journal event")
        return self


class PersistedRun(FrozenModel):
    run_id: NonEmpty
    project_config: ProjectConfig
    spec: RunSpec
    state: RunState
    stages: tuple[StageProjection, ...]


class PersistedAttempt(FrozenModel):
    stage_id: Identifier
    slot_id: NonEmpty
    spec: AgentRunSpec
    state: AttemptState
    result: AttemptResult | None = None
