"""Normalized worker protocol values with no provider-specific types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from orchestrator.domain.models import (
    AttemptStatus,
    Effort,
    FrozenModel,
    Identifier,
    NonEmpty,
    StrictModel,
)


class OutputStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ArtifactEntry(FrozenModel):
    name: Identifier
    schema_id: Identifier
    content_hash: NonEmpty
    relative_path: NonEmpty | None = None


class ArtifactEnvelope(FrozenModel):
    """Versioned worker output contract, independent of stage success semantics."""

    schema_id: Literal["artifact-envelope-v1"] = "artifact-envelope-v1"
    attempt_id: NonEmpty
    input_revision: NonEmpty
    workspace_revision: str | None = None
    status: OutputStatus
    summary: NonEmpty
    artifacts: tuple[ArtifactEntry, ...] = ()


class WorkerResult(ArtifactEnvelope):
    """A normalized output envelope with provider receipt details."""

    provider_status: str | None = None
    usage: Usage | None = None


class Usage(FrozenModel):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class BackendCapabilities(FrozenModel):
    streaming: bool
    steering: bool
    interruption: bool
    saved_history_inspection: bool
    output_schemas: tuple[str, ...] = ()
    supported_efforts: tuple[Effort, ...] = ()
    enforceable_permission_settings: tuple[str, ...] = ()
    unavailable_controls: tuple[tuple[str, str], ...] = ()


class PreflightIssue(StrictModel):
    code: Identifier
    message: NonEmpty
    setting: str | None = None


class PreflightResult(StrictModel):
    accepted: bool
    issues: list[PreflightIssue] = Field(default_factory=list)


class WorkerHandle(FrozenModel):
    handle_id: NonEmpty
    backend: Identifier
    backend_version: NonEmpty
    attempt_id: NonEmpty
    session_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    lifecycle_owner_id: NonEmpty


class WorkerIdentity(FrozenModel):
    backend: Identifier
    attempt_id: NonEmpty
    session_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None


class SteerCommand(FrozenModel):
    command_id: UUID
    attempt_id: NonEmpty
    expected_turn_id: str | None = None
    instruction: NonEmpty


class ControlAck(FrozenModel):
    command_id: UUID
    accepted: bool
    reason: str | None = None


class Reconciliation(FrozenModel):
    known: bool
    status: AttemptStatus | None = None
    terminal_result: WorkerResult | None = None
    detail: str | None = None


class ShutdownReceipt(FrozenModel):
    settled: bool
    detail: str | None = None


class WorkerEventKind(StrEnum):
    STARTED = "started"
    PROGRESS = "progress"
    TERMINAL = "terminal"
    DISCONNECTED = "disconnected"


class WorkerEventBase(FrozenModel):
    attempt_id: NonEmpty
    sequence: int = Field(ge=1)
    occurred_at: datetime | None = None


class WorkerStartedEvent(WorkerEventBase):
    kind: Literal[WorkerEventKind.STARTED]
    handle_id: NonEmpty


class WorkerProgressEvent(WorkerEventBase):
    kind: Literal[WorkerEventKind.PROGRESS]
    message: str
    progress: float | None = Field(default=None, ge=0, le=1)


class WorkerTerminalEvent(WorkerEventBase):
    kind: Literal[WorkerEventKind.TERMINAL]
    result: WorkerResult


class WorkerDisconnectedEvent(WorkerEventBase):
    kind: Literal[WorkerEventKind.DISCONNECTED]
    reason: NonEmpty


type WorkerEvent = Annotated[
    WorkerStartedEvent | WorkerProgressEvent | WorkerTerminalEvent | WorkerDisconnectedEvent,
    Field(discriminator="kind"),
]
