"""The provider-neutral seam implemented by worker adapters."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol
from uuid import UUID

from orchestrator.domain.backend import (
    BackendCapabilities,
    ControlAck,
    PreflightResult,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerEvent,
    WorkerHandle,
    WorkerIdentity,
)
from orchestrator.domain.models import AgentRunSpec


class WorkerBackend(Protocol):
    async def capabilities(self) -> BackendCapabilities: ...

    async def preflight(self, spec: AgentRunSpec) -> PreflightResult: ...

    async def start(self, spec: AgentRunSpec) -> WorkerHandle: ...

    def events(self, handle: WorkerHandle) -> AsyncIterator[WorkerEvent]: ...

    async def steer(self, handle: WorkerHandle, command: SteerCommand) -> ControlAck: ...

    async def interrupt(self, handle: WorkerHandle, command_id: UUID) -> ControlAck: ...

    async def inspect(self, identity: WorkerIdentity) -> Reconciliation: ...

    async def close(self, handle: WorkerHandle) -> ShutdownReceipt: ...
