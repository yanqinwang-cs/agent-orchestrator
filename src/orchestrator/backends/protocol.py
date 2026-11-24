"""The provider-neutral seam implemented by worker adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from orchestrator.domain.backend import (
    BackendCapabilities,
    ControlAck,
    PreflightContext,
    PreflightResult,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerEvent,
    WorkerHandle,
    WorkerIdentity,
)
from orchestrator.domain.models import AgentRunSpec, FailureClass


class KnownPrelaunchFailure(RuntimeError):
    """A classified failure proven to occur before execution could be submitted."""

    def __init__(self, failure_class: FailureClass, summary: str, *, safe_to_retry: bool) -> None:
        super().__init__(summary)
        self.failure_class = failure_class
        self.safe_to_retry = safe_to_retry


class WorkerBackend(Protocol):
    async def capabilities(self) -> BackendCapabilities: ...

    async def preflight(
        self, spec: AgentRunSpec, context: PreflightContext | None = None
    ) -> PreflightResult: ...

    async def start(
        self,
        spec: AgentRunSpec,
        *,
        preflight_record_id: str | None = None,
        preflight_record_hash: str | None = None,
    ) -> WorkerHandle: ...

    def events(self, handle: WorkerHandle) -> AsyncIterator[WorkerEvent]: ...

    async def steer(self, handle: WorkerHandle, command: SteerCommand) -> ControlAck: ...

    async def interrupt(self, handle: WorkerHandle, command_id: UUID) -> ControlAck: ...

    async def inspect(self, identity: WorkerIdentity) -> Reconciliation: ...

    async def close(self, handle: WorkerHandle) -> ShutdownReceipt: ...
