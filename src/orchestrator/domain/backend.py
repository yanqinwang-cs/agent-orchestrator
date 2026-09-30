"""Normalized worker protocol values with no provider-specific types."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from orchestrator.domain.models import (
    AttemptStatus,
    Effort,
    FailureClass,
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


class WorkerHandle(FrozenModel):
    handle_id: NonEmpty
    backend: Identifier
    backend_version: NonEmpty
    attempt_id: NonEmpty
    session_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    lifecycle_owner_id: NonEmpty


class PreflightFact(StrictModel):
    """A sanitized, provider-neutral fact observed before worker execution."""

    key: Identifier
    value: str | bool | int | None = None
    state: Literal["verified", "unverified", "unsupported", "not_applicable"]
    reason: str | None = None
    evidence_ref: str | None = None


class BackendPreflightSnapshot(FrozenModel):
    """Effective preparation evidence; values must be sanitized before construction."""

    schema_version: Literal[1] = 1
    preparation_id: NonEmpty
    owner_id: NonEmpty | None = None
    observed_at: datetime
    runtime: tuple[PreflightFact, ...] = ()
    binding: tuple[PreflightFact, ...] = ()
    auth: tuple[PreflightFact, ...] = ()
    permissions: tuple[PreflightFact, ...] = ()
    capabilities: tuple[PreflightFact, ...] = ()
    ownership: tuple[PreflightFact, ...] = ()
    provenance: tuple[PreflightFact, ...] = ()
    recovery: tuple[PreflightFact, ...] = ()

    @model_validator(mode="after")
    def reject_secret_facts(self) -> BackendPreflightSnapshot:
        sensitive = ("token", "secret", "password", "cookie", "credential", "private_key")
        facts = (
            *self.runtime,
            *self.binding,
            *self.auth,
            *self.permissions,
            *self.capabilities,
            *self.ownership,
            *self.provenance,
            *self.recovery,
        )
        if any(any(part in fact.key.lower() for part in sensitive) for fact in facts):
            raise ValueError("preflight facts cannot contain secret-bearing fields")
        return self


class PreflightContext(FrozenModel):
    """Coordinator-owned identity and resolved constraints for one preparation."""

    preparation_id: NonEmpty
    record_id: NonEmpty
    project_path: NonEmpty
    required_outputs: tuple[NonEmpty, ...]
    binding_id: NonEmpty | None = None


class PreflightResult(StrictModel):
    accepted: bool
    issues: list[PreflightIssue] = Field(default_factory=list)
    snapshot: BackendPreflightSnapshot | None = None
    prepared_handle: WorkerHandle | None = None


class WorkerIdentity(FrozenModel):
    backend: Identifier
    backend_version: NonEmpty | None = None
    attempt_id: NonEmpty
    session_id: str | None = None
    thread_id: str | None = None
    turn_id: str | None = None
    lifecycle_owner_id: NonEmpty | None = None


class SteerCommand(FrozenModel):
    command_id: UUID
    attempt_id: NonEmpty
    expected_turn_id: str | None = None
    instruction: NonEmpty
    effective_input_revision: str | None = None


class ControlAck(FrozenModel):
    command_id: UUID
    accepted: bool
    supported: bool = True
    reason: str | None = None


class Reconciliation(FrozenModel):
    known: bool
    status: AttemptStatus | None = None
    terminal_result: WorkerResult | None = None
    failure_class: FailureClass | None = None
    safe_to_retry: bool = False
    effective_input_revision: str | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def require_known_status(self) -> Reconciliation:
        if self.known != (self.status is not None):
            raise ValueError("known reconciliation must include status and unknown must omit it")
        if self.terminal_result is not None and self.status != AttemptStatus.SUCCEEDED:
            raise ValueError("terminal result is valid only for a succeeded attempt")
        return self


class ShutdownReceipt(FrozenModel):
    settled: bool
    detail: str | None = None


class WorkerEventKind(StrEnum):
    STARTED = "started"
    PROGRESS = "progress"
    TERMINAL = "terminal"
    FAILED = "failed"
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


class WorkerFailureEvent(WorkerEventBase):
    """A known terminal execution failure, classified before retry decisions."""

    kind: Literal[WorkerEventKind.FAILED]
    failure_class: FailureClass
    summary: NonEmpty
    safe_to_retry: bool = False


type WorkerEvent = Annotated[
    WorkerStartedEvent
    | WorkerProgressEvent
    | WorkerTerminalEvent
    | WorkerDisconnectedEvent
    | WorkerFailureEvent,
    Field(discriminator="kind"),
]
