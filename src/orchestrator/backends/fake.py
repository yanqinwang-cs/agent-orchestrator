"""Controllable fake worker adapter for deterministic tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
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
from orchestrator.domain.models import AgentRunSpec, Effort


@dataclass(frozen=True)
class ScriptedAck:
    accepted: bool = True
    reason: str | None = None


@dataclass(frozen=True)
class AttemptScript:
    events: tuple[WorkerEvent, ...]
    steer_acks: tuple[ScriptedAck, ...] = (ScriptedAck(),)
    interrupt_acks: tuple[ScriptedAck, ...] = (ScriptedAck(),)


class FakeClock:
    """A manually advanced monotonic clock; it never sleeps or reads wall time."""

    def __init__(self, initial: float = 0.0) -> None:
        if initial < 0:
            raise ValueError("initial time must be non-negative")
        self._now = initial

    @property
    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self._now += seconds
        return self._now


class FakeBackend:
    """Streams a scripted event only after the test releases its event barrier."""

    def __init__(
        self,
        scripts: Mapping[str, AttemptScript],
        *,
        clock: FakeClock | None = None,
        backend_id: str = "fake",
    ) -> None:
        self._scripts = dict(scripts)
        self.clock = clock or FakeClock()
        self.backend_id = backend_id
        self._handles: dict[str, WorkerHandle] = {}
        self._consumed: set[str] = set()
        self._permits: dict[tuple[str, int], asyncio.Event] = {}
        self._waiting: dict[tuple[str, int], asyncio.Event] = {}
        self._next_release: dict[str, int] = {}
        self._steer_index: dict[str, int] = {}
        self._interrupt_index: dict[str, int] = {}

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            streaming=True,
            steering=True,
            interruption=True,
            saved_history_inspection=False,
            output_schemas=("artifact-envelope-v1",),
            supported_efforts=tuple(Effort),
            enforceable_permission_settings=("sandbox", "approval_mode"),
        )

    async def preflight(self, spec: AgentRunSpec) -> PreflightResult:
        if spec.backend != self.backend_id:
            from orchestrator.domain.backend import PreflightIssue

            return PreflightResult(
                accepted=False,
                issues=[
                    PreflightIssue(code="backend_mismatch", message="spec targets another backend")
                ],
            )
        return PreflightResult(accepted=True)

    async def start(self, spec: AgentRunSpec) -> WorkerHandle:
        attempt_id = spec.attempt_id
        if attempt_id not in self._scripts:
            raise KeyError(f"no fake script registered for attempt {attempt_id}")
        if attempt_id in self._handles:
            raise RuntimeError(f"fake start is not idempotent for attempt {attempt_id}")
        handle = WorkerHandle(
            handle_id=f"fake:{attempt_id}",
            backend=self.backend_id,
            backend_version="scripted-v1",
            attempt_id=attempt_id,
            session_id=f"session:{attempt_id}",
            thread_id=f"thread:{attempt_id}",
            turn_id=f"turn:{attempt_id}",
            lifecycle_owner_id="fake-owner",
        )
        self._handles[attempt_id] = handle
        self._next_release[attempt_id] = 0
        for index, _ in enumerate(self._scripts[attempt_id].events):
            self._permits[(attempt_id, index)] = asyncio.Event()
            self._waiting[(attempt_id, index)] = asyncio.Event()
        return handle

    async def events(self, handle: WorkerHandle) -> AsyncIterator[WorkerEvent]:
        attempt_id = handle.attempt_id
        if self._handles.get(attempt_id) != handle:
            raise ValueError("unknown or mismatched fake worker handle")
        if attempt_id in self._consumed:
            raise RuntimeError("fake event stream has a single consumer")
        self._consumed.add(attempt_id)
        script = self._scripts[attempt_id]
        for index, event in enumerate(script.events):
            self._waiting[(attempt_id, index)].set()
            await self._permits[(attempt_id, index)].wait()
            yield event

    async def wait_until_waiting(self, attempt_id: str, index: int) -> None:
        try:
            barrier = self._waiting[(attempt_id, index)]
        except KeyError as error:
            raise ValueError("start the attempt and register that event index first") from error
        await barrier.wait()

    def release_next(self, attempt_id: str) -> None:
        index = self._next_release.get(attempt_id)
        if index is None:
            raise ValueError(f"attempt {attempt_id} has not started")
        permit = self._permits.get((attempt_id, index))
        if permit is None:
            raise ValueError(f"attempt {attempt_id} has no event {index} to release")
        permit.set()
        self._next_release[attempt_id] = index + 1

    async def steer(self, handle: WorkerHandle, command: SteerCommand) -> ControlAck:
        return self._ack(handle, command.command_id, steer=True)

    async def interrupt(self, handle: WorkerHandle, command_id: UUID) -> ControlAck:
        return self._ack(handle, command_id, steer=False)

    async def inspect(self, identity: WorkerIdentity) -> Reconciliation:
        known = identity.attempt_id in self._handles
        return Reconciliation(
            known=known, detail="scripted fake state" if known else "unknown attempt"
        )

    async def close(self, handle: WorkerHandle) -> ShutdownReceipt:
        if self._handles.get(handle.attempt_id) != handle:
            return ShutdownReceipt(settled=False, detail="unknown handle")
        return ShutdownReceipt(settled=True, detail="fake handle closed")

    def _ack(self, handle: WorkerHandle, command_id: UUID, *, steer: bool) -> ControlAck:
        script = self._scripts.get(handle.attempt_id)
        if script is None or self._handles.get(handle.attempt_id) != handle:
            return ControlAck(command_id=command_id, accepted=False, reason="unknown handle")
        counters = self._steer_index if steer else self._interrupt_index
        acks = script.steer_acks if steer else script.interrupt_acks
        index = counters.get(handle.attempt_id, 0)
        counters[handle.attempt_id] = index + 1
        if index >= len(acks):
            return ControlAck(
                command_id=command_id, accepted=False, reason="no scripted acknowledgement"
            )
        result = acks[index]
        return ControlAck(command_id=command_id, accepted=result.accepted, reason=result.reason)
