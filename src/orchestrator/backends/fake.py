"""Controllable fake worker adapter for deterministic tests."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from orchestrator.backends.protocol import KnownPrelaunchFailure
from orchestrator.domain.backend import (
    BackendCapabilities,
    ControlAck,
    PreflightContext,
    PreflightResult,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerEvent,
    WorkerFailureEvent,
    WorkerHandle,
    WorkerIdentity,
    WorkerResult,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import AgentRunSpec, AttemptStatus, Effort, FailureClass


@dataclass(frozen=True)
class ScriptedAck:
    accepted: bool = True
    reason: str | None = None
    supported: bool = True
    unknown: bool = False
    disconnect: bool = False
    barrier: bool = False
    consumed: bool = True


@dataclass(frozen=True)
class AttemptScript:
    events: tuple[WorkerEvent, ...]
    steer_acks: tuple[ScriptedAck, ...] = (ScriptedAck(),)
    interrupt_acks: tuple[ScriptedAck, ...] = (ScriptedAck(),)
    start_failure: ScriptedFailure | None = None
    start_barrier: bool = False
    event_barrier: bool | None = None
    close_receipts: tuple[ShutdownReceipt, ...] = (ShutdownReceipt(settled=True),)
    reconciliations: tuple[Reconciliation, ...] = ()


@dataclass(frozen=True)
class ScriptedFailure:
    failure_class: FailureClass
    summary: str
    safe_to_retry: bool = True


class FakeBackendFailure(KnownPrelaunchFailure):
    """A scripted failure known to have happened before a worker was started."""


class FakeClock:
    """A manually advanced monotonic clock; it never sleeps or reads wall time."""

    def __init__(
        self,
        initial: float = 0.0,
        *,
        origin: datetime | None = None,
    ) -> None:
        if initial < 0:
            raise ValueError("initial time must be non-negative")
        self._now = initial
        self._origin = (origin or datetime(2000, 1, 1, tzinfo=UTC)).astimezone(UTC)
        self._changed = asyncio.Event()

    @property
    def now(self) -> float:
        return self._now

    def advance(self, seconds: float) -> float:
        if seconds < 0:
            raise ValueError("clock cannot move backwards")
        self._now += seconds
        changed = self._changed
        self._changed = asyncio.Event()
        changed.set()
        return self._now

    @property
    def utc_now(self) -> datetime:
        return self._origin + timedelta(seconds=self._now)

    async def wait_until_advanced(self, after: float) -> float:
        while self._now <= after:
            changed = self._changed
            await changed.wait()
        return self._now


class FakeBackend:
    """Streams a scripted event only after the test releases its event barrier."""

    def __init__(
        self,
        scripts: Mapping[str, AttemptScript] | None = None,
        *,
        clock: FakeClock | None = None,
        backend_id: str = "fake",
        script_factory: Callable[[AgentRunSpec], AttemptScript] | None = None,
        auto_release: bool = False,
    ) -> None:
        self._scripts = dict(scripts or {})
        self._script_factory = script_factory
        self.auto_release = auto_release
        self.clock = clock or FakeClock()
        self.backend_id = backend_id
        self._handles: dict[str, WorkerHandle] = {}
        self._specs: dict[str, AgentRunSpec] = {}
        self.start_calls: list[str] = []
        self._consumed: set[str] = set()
        self._permits: dict[tuple[str, int], asyncio.Event] = {}
        self._waiting: dict[tuple[str, int], asyncio.Event] = {}
        self._next_release: dict[str, int] = {}
        self._start_permits: dict[str, asyncio.Event] = {}
        self._start_waiting: dict[str, asyncio.Event] = {}
        self._start_registered = asyncio.Event()
        self._specs_changed = asyncio.Event()
        self._steer_index: dict[str, int] = {}
        self._interrupt_index: dict[str, int] = {}
        self._close_index: dict[str, int] = {}
        self._inspect_index: dict[str, int] = {}
        self._known_status: dict[str, AttemptStatus] = {}
        self._terminal_results: dict[str, WorkerResult] = {}
        self._failure_details: dict[str, tuple[FailureClass, bool]] = {}
        self._effective_input_revisions: dict[str, str] = {}
        self._closed: set[str] = set()
        self._control_waiting: dict[tuple[str, str, int], asyncio.Event] = {}
        self._control_permits: dict[tuple[str, str, int], asyncio.Event] = {}
        self._seen_controls: dict[UUID, ControlAck] = {}

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

    async def preflight(
        self, spec: AgentRunSpec, context: PreflightContext | None = None
    ) -> PreflightResult:
        if spec.backend != self.backend_id:
            from orchestrator.domain.backend import PreflightIssue

            return PreflightResult(
                accepted=False,
                issues=[
                    PreflightIssue(code="backend_mismatch", message="spec targets another backend")
                ],
            )
        return PreflightResult(accepted=True)

    async def start(
        self,
        spec: AgentRunSpec,
        *,
        preflight_record_id: str | None = None,
        preflight_record_hash: str | None = None,
    ) -> WorkerHandle:
        attempt_id = spec.attempt_id
        script = self._scripts.get(attempt_id)
        if script is None and self._script_factory is not None:
            script = self._script_factory(spec)
            self._scripts[attempt_id] = script
        if script is None:
            raise KeyError(f"no fake script registered for attempt {attempt_id}")
        if attempt_id in self._handles:
            raise RuntimeError(f"fake start is not idempotent for attempt {attempt_id}")
        self.start_calls.append(attempt_id)
        self._start_permits[attempt_id] = asyncio.Event()
        self._start_waiting[attempt_id] = asyncio.Event()
        self._start_waiting[attempt_id].set()
        registered = self._start_registered
        self._start_registered = asyncio.Event()
        registered.set()
        if script.start_barrier:
            await self._start_permits[attempt_id].wait()
        if script.start_failure is not None:
            raise FakeBackendFailure(
                script.start_failure.failure_class,
                script.start_failure.summary,
                safe_to_retry=script.start_failure.safe_to_retry,
            )
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
        self._specs[attempt_id] = spec
        self._known_status[attempt_id] = AttemptStatus.RUNNING
        self._closed.discard(attempt_id)
        self._effective_input_revisions[attempt_id] = self._input_revision(spec)
        changed = self._specs_changed
        self._specs_changed = asyncio.Event()
        changed.set()
        self._next_release[attempt_id] = 0
        for index, _ in enumerate(self._scripts[attempt_id].events):
            self._permits[(attempt_id, index)] = asyncio.Event()
            self._waiting[(attempt_id, index)] = asyncio.Event()
        return handle

    async def wait_until_start_waiting(self, attempt_id: str) -> None:
        """Wait until start has reached its scripted acknowledgement barrier."""
        while attempt_id not in self._start_waiting:
            registered = self._start_registered
            await registered.wait()
        barrier = self._start_waiting[attempt_id]
        await barrier.wait()

    def release_start(self, attempt_id: str) -> None:
        """Release a scripted launch acknowledgement."""
        try:
            permit = self._start_permits[attempt_id]
        except KeyError as error:
            raise ValueError(f"attempt {attempt_id} has not started") from error
        permit.set()

    async def wait_until_started_stage(self, stage_id: str) -> str:
        """Return the first started attempt for a workflow stage."""
        while True:
            matches = sorted(
                attempt_id for attempt_id, spec in self._specs.items() if spec.stage_id == stage_id
            )
            if matches:
                return matches[0]
            changed = self._specs_changed
            await changed.wait()

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
            release_automatically = (
                self.auto_release if script.event_barrier is None else not script.event_barrier
            )
            if release_automatically:
                self.release_next(attempt_id)
            await self._permits[(attempt_id, index)].wait()
            if attempt_id in self._closed:
                self._known_status[attempt_id] = AttemptStatus.CANCELLED
                return
            if isinstance(event, WorkerTerminalEvent):
                result = event.result
                if result.input_revision in {"effective", "*"}:
                    result = result.model_copy(
                        update={"input_revision": self._effective_input_revisions[attempt_id]}
                    )
                    event = event.model_copy(update={"result": result})
                self._known_status[attempt_id] = AttemptStatus.SUCCEEDED
                self._terminal_results[attempt_id] = result
            elif isinstance(event, WorkerFailureEvent):
                self._known_status[attempt_id] = AttemptStatus.FAILED
                self._failure_details[attempt_id] = (event.failure_class, event.safe_to_retry)
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
        return await self._ack(handle, command.command_id, steer=True, command=command)

    async def interrupt(self, handle: WorkerHandle, command_id: UUID) -> ControlAck:
        return await self._ack(handle, command_id, steer=False)

    async def inspect(self, identity: WorkerIdentity) -> Reconciliation:
        handle = self._handles.get(identity.attempt_id)
        if handle is not None and (
            handle.backend != identity.backend
            or (identity.session_id is not None and handle.session_id != identity.session_id)
            or (identity.thread_id is not None and handle.thread_id != identity.thread_id)
            or (identity.turn_id is not None and handle.turn_id != identity.turn_id)
            or (
                identity.lifecycle_owner_id is not None
                and handle.lifecycle_owner_id != identity.lifecycle_owner_id
            )
        ):
            return Reconciliation(known=False, detail="persisted worker identity did not match")
        script = self._scripts.get(identity.attempt_id)
        if script is not None and script.reconciliations:
            index = self._inspect_index.get(identity.attempt_id, 0)
            self._inspect_index[identity.attempt_id] = index + 1
            reconciliation = script.reconciliations[min(index, len(script.reconciliations) - 1)]
            if reconciliation.known and reconciliation.status is not None:
                self._known_status[identity.attempt_id] = reconciliation.status
                if reconciliation.terminal_result is not None:
                    self._terminal_results[identity.attempt_id] = reconciliation.terminal_result
                if reconciliation.status in {
                    AttemptStatus.SUCCEEDED,
                    AttemptStatus.FAILED,
                    AttemptStatus.CANCELLED,
                    AttemptStatus.TIMED_OUT,
                }:
                    for (attempt_id, _event_index), permit in self._permits.items():
                        if attempt_id == identity.attempt_id:
                            permit.set()
            return reconciliation
        status = self._known_status.get(identity.attempt_id)
        if status is None:
            return Reconciliation(known=False, detail="fake backend has no evidence for attempt")
        failure = self._failure_details.get(identity.attempt_id)
        return Reconciliation(
            known=True,
            status=status,
            terminal_result=self._terminal_results.get(identity.attempt_id),
            failure_class=failure[0] if failure else None,
            safe_to_retry=failure[1] if failure else False,
            effective_input_revision=self._effective_input_revisions.get(identity.attempt_id),
            detail="scripted fake state",
        )

    async def close(self, handle: WorkerHandle) -> ShutdownReceipt:
        if self._handles.get(handle.attempt_id) != handle:
            return ShutdownReceipt(settled=False, detail="unknown handle")
        script = self._scripts[handle.attempt_id]
        index = self._close_index.get(handle.attempt_id, 0)
        self._close_index[handle.attempt_id] = index + 1
        if not script.close_receipts:
            return ShutdownReceipt(settled=False, detail="no shutdown receipt was scripted")
        receipt = script.close_receipts[min(index, len(script.close_receipts) - 1)]
        if receipt.settled and self._known_status.get(handle.attempt_id) not in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
        }:
            self._known_status[handle.attempt_id] = AttemptStatus.CANCELLED
        if receipt.settled:
            self._closed.add(handle.attempt_id)
            for (attempt_id, _index), permit in self._permits.items():
                if attempt_id == handle.attempt_id:
                    permit.set()
        return receipt

    async def _ack(
        self,
        handle: WorkerHandle,
        command_id: UUID,
        *,
        steer: bool,
        command: SteerCommand | None = None,
    ) -> ControlAck:
        prior = self._seen_controls.get(command_id)
        if prior is not None:
            return prior
        script = self._scripts.get(handle.attempt_id)
        if script is None or self._handles.get(handle.attempt_id) != handle:
            return ControlAck(command_id=command_id, accepted=False, reason="unknown handle")
        if self._known_status.get(handle.attempt_id) in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLED,
            AttemptStatus.TIMED_OUT,
        }:
            ack = ControlAck(
                command_id=command_id,
                accepted=False,
                reason="worker already terminal",
            )
            self._seen_controls[command_id] = ack
            return ack
        if steer and command is not None and command.expected_turn_id != handle.turn_id:
            ack = ControlAck(command_id=command_id, accepted=False, reason="turn identity mismatch")
            self._seen_controls[command_id] = ack
            return ack
        counters = self._steer_index if steer else self._interrupt_index
        acks = script.steer_acks if steer else script.interrupt_acks
        index = counters.get(handle.attempt_id, 0)
        counters[handle.attempt_id] = index + 1
        control_kind = "steer" if steer else "interrupt"
        key = (handle.attempt_id, control_kind, index)
        waiting = self._control_waiting.setdefault(key, asyncio.Event())
        permit = self._control_permits.setdefault(key, asyncio.Event())
        waiting.set()
        if index >= len(acks):
            ack = ControlAck(
                command_id=command_id, accepted=False, reason="no scripted acknowledgement"
            )
            self._seen_controls[command_id] = ack
            return ack
        result = acks[index]
        if result.barrier:
            await permit.wait()
        if self._known_status.get(handle.attempt_id) in {
            AttemptStatus.SUCCEEDED,
            AttemptStatus.FAILED,
            AttemptStatus.CANCELLED,
            AttemptStatus.TIMED_OUT,
        }:
            ack = ControlAck(
                command_id=command_id,
                accepted=False,
                reason="worker already terminal",
            )
            self._seen_controls[command_id] = ack
            return ack
        if result.disconnect:
            raise ConnectionError("scripted backend disconnect during control")
        if result.unknown:
            raise TimeoutError("scripted control acknowledgement was lost")
        ack = ControlAck(
            command_id=command_id,
            accepted=result.accepted,
            supported=result.supported,
            reason=result.reason,
        )
        self._seen_controls[command_id] = ack
        if (
            steer
            and ack.accepted
            and command is not None
            and result.consumed
            and command.effective_input_revision is not None
        ):
            self._effective_input_revisions[handle.attempt_id] = command.effective_input_revision
        return ack

    async def wait_until_control_waiting(
        self, attempt_id: str, control: Literal["steer", "interrupt"], index: int = 0
    ) -> None:
        key = (attempt_id, control, index)
        waiting = self._control_waiting.setdefault(key, asyncio.Event())
        await waiting.wait()

    def release_control(
        self, attempt_id: str, control: Literal["steer", "interrupt"], index: int = 0
    ) -> None:
        key = (attempt_id, control, index)
        permit = self._control_permits.setdefault(key, asyncio.Event())
        permit.set()

    @staticmethod
    def _input_revision(spec: AgentRunSpec) -> str:
        payload = json.dumps(
            [entry.model_dump(mode="json") for entry in spec.input_manifest],
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
