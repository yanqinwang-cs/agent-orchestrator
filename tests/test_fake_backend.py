import asyncio
from uuid import uuid4

import pytest

from orchestrator.backends.fake import AttemptScript, FakeBackend, FakeClock, ScriptedAck
from orchestrator.domain.backend import (
    OutputStatus,
    SteerCommand,
    WorkerProgressEvent,
    WorkerResult,
    WorkerStartedEvent,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import AgentRunSpec, PermissionSet, SandboxMode


def _spec(attempt_id: str = "attempt-1") -> AgentRunSpec:
    return AgentRunSpec(
        run_id="run-1",
        attempt_id=attempt_id,
        profile_id="reviewer",
        profile_version="1.0.0",
        instructions="Review the patch",
        input_manifest=(),
        backend="fake",
        model_id="fake-model",
        effort="high",
        permissions=PermissionSet(sandbox=SandboxMode.READ_ONLY),
        skills=(),
        tools=("read_files",),
        run_snapshot_hash="a" * 64,
    )


@pytest.mark.asyncio
async def test_fake_backend_releases_scripted_events_in_order() -> None:
    events = (
        WorkerStartedEvent(kind="started", attempt_id="attempt-1", sequence=1, handle_id="h1"),
        WorkerProgressEvent(
            kind="progress", attempt_id="attempt-1", sequence=2, message="reviewing"
        ),
        WorkerTerminalEvent(
            kind="terminal",
            attempt_id="attempt-1",
            sequence=3,
            result=WorkerResult(
                attempt_id="attempt-1",
                input_revision="inputs-v1",
                status=OutputStatus.PASS,
                summary="clean",
            ),
        ),
    )
    backend = FakeBackend(
        {
            "attempt-1": AttemptScript(
                events=events,
                steer_acks=(ScriptedAck(accepted=True),),
                interrupt_acks=(ScriptedAck(accepted=False, reason="already complete"),),
            )
        }
    )
    handle = await backend.start(_spec())
    stream = backend.events(handle)
    received = []
    for index in range(len(events)):
        next_event = asyncio.create_task(anext(stream))
        await backend.wait_until_waiting("attempt-1", index)
        backend.release_next("attempt-1")
        received.append(await next_event)

    assert received == list(events)
    steer_ack = await backend.steer(
        handle,
        SteerCommand(command_id=uuid4(), attempt_id="attempt-1", instruction="Prioritize security"),
    )
    interrupt_ack = await backend.interrupt(handle, uuid4())
    assert steer_ack.accepted is False
    assert steer_ack.reason == "worker already terminal"
    assert interrupt_ack.accepted is False
    assert interrupt_ack.reason == "worker already terminal"


def test_fake_clock_advances_only_when_controlled() -> None:
    clock = FakeClock(initial=3)
    assert clock.now == 3
    assert clock.advance(2.5) == 5.5
    with pytest.raises(ValueError, match="cannot move backwards"):
        clock.advance(-1)
