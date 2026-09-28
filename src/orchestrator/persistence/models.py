"""Versioned records and commands for the durable runtime ledger."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from orchestrator.domain.models import (
    AgentRunSpec,
    Artifact,
    AttemptState,
    Event,
    FrozenModel,
    Handoff,
    Identifier,
    NonEmpty,
    OutboxStatus,
    ProjectConfig,
    ReservationStatus,
    RunSpec,
    RunState,
    RunStatus,
    StageStatus,
)


class StageUpdate(FrozenModel):
    stage_id: Identifier
    status: StageStatus


class StageProjection(FrozenModel):
    schema_version: Literal[1] = 1
    stage_id: Identifier
    status: StageStatus
    updated_at: datetime


class RunProjectionUpdate(FrozenModel):
    status: RunStatus | None = None
    active_stages: tuple[Identifier, ...] | None = None
    attempts_used: int | None = Field(default=None, ge=0)
    elapsed_seconds: float | None = Field(default=None, ge=0)


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
    events: tuple[Event, ...] = ()
    outbox_actions: tuple[OutboxIntent, ...] = ()
    outbox_outcomes: tuple[OutboxOutcomeChange, ...] = ()
    reservations: tuple[ReservationChange, ...] = ()
    handoffs: tuple[Handoff, ...] = ()
    artifacts: tuple[ArtifactRegistration, ...] = ()

    @model_validator(mode="after")
    def reject_duplicate_targets(self) -> LedgerMutation:
        stage_ids = [stage.stage_id for stage in self.stage_updates]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("a mutation can update each stage only once")
        attempt_ids = [item.spec.attempt_id for item in self.attempt_creations]
        attempt_ids.extend(item.attempt_id for item in self.attempt_updates)
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
