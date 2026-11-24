"""Regression tests for reproduced Codex backend bugs, driven by the offline SDK stand-in."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace

import pytest
from openai_codex.generated.v2_all import (
    AgentMessageDeltaNotification,
    CommandExecutionOutputDeltaNotification,
    ReasoningSummaryTextDeltaNotification,
    TurnCompletedNotification,
)
from test_codex_backend_lifecycle import (
    REPORT,
    _prepare_and_start,
    _record_accepted_preflight,
    lifecycle,
)

from orchestrator.backends.codex_backend import CodexBackend
from orchestrator.backends.protocol import KnownPrelaunchFailure
from orchestrator.domain.backend import (
    WorkerDisconnectedEvent,
    WorkerStartedEvent,
    WorkerTerminalEvent,
)


@pytest.fixture(autouse=True)
def _offline_cli(monkeypatch):
    monkeypatch.setattr(
        CodexBackend, "_inspect_cli", staticmethod(lambda: ("/x/codex", "0.159.2", "a" * 64))
    )


def _completed(client, items):
    turn = {"id": client.turn_id, "status": "completed", "items": items}
    return SimpleNamespace(
        method="turn/completed",
        payload=TurnCompletedNotification.model_validate(
            {"threadId": client.thread_id, "turn": turn}
        ),
    )


def _delta(client, method, model, **fields):
    ids = {"threadId": client.thread_id, "turnId": client.turn_id, "itemId": "i"}
    return SimpleNamespace(method=method, payload=model.model_validate({**ids, **fields}))


async def _drain(lifecycle, handle):
    return [event async for event in lifecycle.backend.events(handle)]


@pytest.mark.asyncio
async def test_wrapped_sdk_items_do_not_pull_stream_deltas_into_the_report(lifecycle) -> None:
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    for note in (
        _delta(
            client,
            "item/reasoning/summaryTextDelta",
            ReasoningSummaryTextDeltaNotification,
            delta="Thinking... ",
            summaryIndex=0,
        ),
        _delta(
            client,
            "item/commandExecution/outputDelta",
            CommandExecutionOutputDeltaNotification,
            delta="README.md\n",
        ),
        _delta(
            client, "item/agentMessage/delta", AgentMessageDeltaNotification, delta=REPORT.decode()
        ),
    ):
        client.turn_notifications.put_nowait(note)
    client.turn_notifications.put_nowait(
        _completed(client, [{"type": "agentMessage", "id": "i", "text": REPORT.decode()}])
    )

    events = await _drain(lifecycle, handle)

    assert isinstance(events[-1], WorkerTerminalEvent)


@pytest.mark.asyncio
async def test_report_is_rebuilt_from_agent_message_deltas_only(lifecycle) -> None:
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    for note in (
        _delta(
            client,
            "item/commandExecution/outputDelta",
            CommandExecutionOutputDeltaNotification,
            delta="README.md\n",
        ),
        _delta(
            client, "item/agentMessage/delta", AgentMessageDeltaNotification, delta=REPORT.decode()
        ),
    ):
        client.turn_notifications.put_nowait(note)
    client.turn_notifications.put_nowait(_completed(client, []))

    events = await _drain(lifecycle, handle)

    assert isinstance(events[-1], WorkerTerminalEvent)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("item_type", "fields"),
    [
        (
            "mcpToolCall",
            {"server": "evil", "tool": "write", "status": "completed", "arguments": {}},
        ),
    ],
)
async def test_forbidden_tool_call_in_real_sdk_items_rejects_the_completed_turn(
    lifecycle, item_type, fields
) -> None:
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    items = [
        {"type": item_type, "id": "i1", **fields},
        {"type": "agentMessage", "id": "i2", "text": REPORT.decode()},
    ]
    client.turn_notifications.put_nowait(_completed(client, items))

    events = await _drain(lifecycle, handle)

    assert isinstance(events[-1], WorkerDisconnectedEvent)


@pytest.mark.asyncio
async def test_close_wakes_a_reader_waiting_for_events(lifecycle) -> None:
    _, handle = await _prepare_and_start(lifecycle)
    stream = lifecycle.backend.events(handle)
    assert isinstance(await stream.__anext__(), WorkerStartedEvent)
    waiting = asyncio.ensure_future(stream.__anext__())
    await asyncio.sleep(0.05)

    await lifecycle.backend.close(handle)

    done, _pending = await asyncio.wait({waiting}, timeout=3)
    waiting.cancel()
    assert done, "events() never ended after close()"
    assert isinstance(waiting.result(), WorkerDisconnectedEvent)


@pytest.mark.asyncio
async def test_caller_timeout_on_close_is_not_swallowed(lifecycle) -> None:
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    owner = lifecycle.owners[-1]
    terminate = owner.terminate_child

    def slow_terminate():
        time.sleep(1.5)
        return terminate()

    owner.terminate_child = slow_terminate
    started = time.monotonic()

    with pytest.raises(TimeoutError):
        await asyncio.wait_for(lifecycle.backend.close(result.prepared_handle), timeout=0.1)

    assert time.monotonic() - started < 1.0


@pytest.mark.asyncio
async def test_timeout_before_the_turn_is_sent_is_a_known_prelaunch_failure(
    lifecycle, monkeypatch
) -> None:
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    client = lifecycle.clients[-1]
    request = client.request

    async def hang_on_config(method, params, *, response_model):
        if method == "config/read":
            await asyncio.sleep(3600)
        return await request(method, params, response_model=response_model)

    client.request = hang_on_config
    original = CodexBackend._bounded_sdk

    async def quick(self, awaitable, timeout):
        return await original(self, awaitable, min(timeout, 0.05))

    monkeypatch.setattr(CodexBackend, "_bounded_sdk", quick)

    with pytest.raises(KnownPrelaunchFailure):
        await lifecycle.backend.start(
            lifecycle.spec, preflight_record_id=record_id, preflight_record_hash=record_hash
        )

    assert client.turn_count == 0
