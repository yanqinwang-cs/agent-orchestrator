"""Exercise actual Deep Agents/LangGraph, never live provider calls."""

import asyncio
import socket
import subprocess
from dataclasses import replace

import pytest

pytest.importorskip("deepagents", reason="install the optional harness extra")

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: E402
from test_harness_records import price, spec  # noqa: E402

from agent_harness.adapter import OfflineBinding, OfflineHarness  # noqa: E402
from agent_harness.fakes import OfflineChatModel  # noqa: E402
from agent_harness.records import Agent, Bounds, ModelBinding, Outcome  # noqa: E402


@pytest.fixture(autouse=True)
def no_network_or_shell(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline harness attempted network or shell access")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    # Even a developer's ambient tracing settings cannot export invocation content.
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "fixture-not-a-real-key")


def binding(model="a", factory=None):
    return OfflineBinding(
        ModelBinding(provider="offline", model=model, revision="1"),
        factory or (lambda: OfflineChatModel(label=model)),
    )


def with_agents(original, agents, **changes):
    return type(original).model_validate({**original.model_dump(), "agents": agents, **changes})


async def test_replace_model_without_changing_instructions_or_topology():
    models = [OfflineChatModel(label="a"), OfflineChatModel(label="b")]
    bindings = (binding("a", lambda: models[0]), binding("b", lambda: models[1]))
    original = spec()
    swapped = with_agents(
        original,
        (original.agents[0].model_copy(update={"binding": bindings[1].identity}),),
        invocation_id="run-2",
    )
    host = OfflineHarness(bindings)
    first = await host.start(original).outcome()
    second = await host.start(swapped).outcome()
    assert [o.status for o in (first, second)] == ["completed", "completed"]
    assert [o.outputs[0].text for o in (first, second)] == ["a:hello", "b:hello"]
    assert [(m.type, m.content) for m in models[0].seen[0]] == [
        (m.type, m.content) for m in models[1].seen[0]
    ]
    assert isinstance(models[0].seen[0][0], SystemMessage)
    assert "Respond" in models[0].seen[0][0].text
    assert first.invocation_fingerprint == original.fingerprint
    assert original.agents[0].binding.model == "a"
    assert first.effects == second.effects == "local_settled"
    assert first.steps == second.steps == 1
    assert {v.component for v in first.versions} >= {"deepagents", "langgraph"}
    assert Outcome.model_validate_json(first.model_dump_json()) == first


async def test_two_agents_handoff_uses_first_output_as_second_input():
    models = [OfflineChatModel(label="a"), OfflineChatModel(label="b")]
    bindings = (binding("a", lambda: models[0]), binding("b", lambda: models[1]))
    original = spec()
    invocation = with_agents(
        original,
        (
            original.agents[0],
            Agent(name="two", instructions="Review the first output", binding=bindings[1].identity),
        ),
        bounds=Bounds(steps=2),
    )
    result = await OfflineHarness(bindings).start(invocation).outcome()
    assert result.status == "completed"
    assert [o.text for o in result.outputs] == ["a:hello", "b:a:hello"]
    assert isinstance(models[1].seen[0][-1], HumanMessage)
    assert models[1].seen[0][-1].content == "a:hello"
    assert result.steps == 2
    assert models[0].bound_tools == models[1].bound_tools == []


async def test_declared_tool_and_usage_price_round_trip():
    model = OfflineChatModel(
        replies=(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "uppercase",
                        "args": {"text": "hello"},
                        "id": "call-1",
                    }
                ],
                usage_metadata={"input_tokens": 60, "output_tokens": 10, "total_tokens": 70},
            ),
            AIMessage(
                content="HELLO",
                usage_metadata={
                    "input_tokens": 40,
                    "output_tokens": 10,
                    "total_tokens": 50,
                },
            ),
        )
    )
    original = spec(prices=(price(),))
    invocation = with_agents(
        original, (original.agents[0].model_copy(update={"tools": ("uppercase",)}),)
    )
    result = await OfflineHarness((binding(factory=lambda: model),)).start(invocation).outcome()
    assert result.status == "completed"
    assert result.outputs[0].text == "HELLO"
    assert model.seen[1][-1].content == "HELLO"  # Tool actually ran in LangGraph.
    assert all(names == ("uppercase",) for names in model.bound_tools)
    assert result.steps == 3
    assert result.outputs[0].usage.input_tokens == 100
    assert str(result.outputs[0].estimate.amount) == "0.00032"
    assert result.outputs[0].estimate.kind == "estimate"
    assert result.elapsed_seconds >= 0


@pytest.mark.parametrize(
    "name",
    [
        "execute",
        "task",
        "write_file",
        "read_file",
        "edit_file",
        "ls",
        "glob",
        "grep",
        "write_todos",
        "uppercase",
        "unknown_tool",
    ],
)
async def test_undeclared_tools_are_never_executed(name):
    model = OfflineChatModel(
        replies=(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": name,
                        "args": {},
                        "id": "denied",
                    }
                ],
            ),
        )
    )
    result = await OfflineHarness((binding(factory=lambda: model),)).start(spec()).outcome()
    assert result.status == "failed"
    assert result.failure == "permission_denied"
    assert model.calls == 1
    assert model.bound_tools == []
    assert result.outputs == ()


@pytest.mark.parametrize("case", ["capability", "binding", "tool"])
async def test_preflight_rejection_before_model_factory(case):
    calls = []
    b = binding(factory=lambda: calls.append(1))
    original = spec()
    agent = original.agents[0]
    changes = {
        "capability": {"required_capabilities": ("images",)},
        "binding": {"binding": b.identity.model_copy(update={"model": "missing"})},
        "tool": {"tools": ("execute",)},
    }
    result = (
        await OfflineHarness((b,))
        .start(with_agents(original, (agent.model_copy(update=changes[case]),)))
        .outcome()
    )
    assert result.status == "rejected"
    assert result.effects == "not_started"
    assert result.steps == 0
    assert calls == []
    assert [e.kind for e in result.evidence] == ["terminal", "effects"]


async def test_failure_sanitized_no_fallback_and_duplicate_identity_never_replayed():
    model = OfflineChatModel(fail=True)
    host = OfflineHarness((binding(factory=lambda: model),))
    invocation = spec()
    result = await host.start(invocation).outcome()
    assert result.status == "failed"
    assert result.failure == "adapter_failure"
    assert "secret-looking" not in result.model_dump_json()
    assert model.calls == 1
    with pytest.raises(ValueError, match="replay"):
        host.start(invocation)
    assert model.calls == 1


async def test_global_step_bound_covers_tools_and_handoff():
    model = OfflineChatModel(
        replies=(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "uppercase",
                        "args": {"text": "hello"},
                        "id": "1",
                    }
                ],
            ),
        )
    )
    original = spec(bounds=Bounds(steps=1))
    invocation = with_agents(
        original, (original.agents[0].model_copy(update={"tools": ("uppercase",)}),)
    )
    result = await OfflineHarness((binding(factory=lambda: model),)).start(invocation).outcome()
    assert result.status == "limited"
    assert result.steps == 1
    assert model.calls == 1
    second = OfflineChatModel()
    invocation = with_agents(
        original,
        (
            original.agents[0],
            Agent(name="two", instructions="Review", binding=binding("b").identity),
        ),
    )
    host = OfflineHarness((binding(), binding("b", lambda: second)))
    result = await host.start(invocation).outcome()
    assert result.status == "limited"
    assert len(result.outputs) == 1
    assert second.calls == 0


async def test_timeout_separates_request_ack_terminal_and_effects():
    model = OfflineChatModel(delay=0.2)
    invocation = spec(bounds=Bounds(seconds=0.02))
    result = await OfflineHarness((binding(factory=lambda: model),)).start(invocation).outcome()
    assert result.status == "timed_out"
    assert result.elapsed_seconds < 0.5
    assert result.effects == "local_settled"
    assert [e.kind for e in result.evidence] == [
        "started",
        "stop_requested",
        "stop_acknowledged",
        "terminal",
        "effects",
    ]
    assert result.evidence[1].actor == "host"
    assert result.evidence[1].request_id == result.evidence[2].request_id
    assert model.calls == 0


async def test_explicit_stop_and_idempotent_request():
    model = OfflineChatModel(delay=0.2)
    handle = OfflineHarness((binding(factory=lambda: model),)).start(spec())
    await model.wait_entered()
    assert handle.stop("stop-1") == "stop-1"
    assert handle.stop("stop-2") == "stop-1"
    result = await handle.outcome()
    assert result.status == "cancelled"
    assert result.evidence[1].actor == "caller"
    assert result.evidence[1].request_id == "stop-1"
    assert handle.stop() is None
    assert result.effects == "local_settled"
    assert model.calls == 0


async def test_missing_ack_remains_uncertain_no_replay_or_false_remote_settlement():
    model = OfflineChatModel(delay=0.1, acknowledge_stop=False)
    host = OfflineHarness((binding(factory=lambda: model),))
    invocation = spec(bounds=Bounds(stop_grace_seconds=0.01))
    handle = host.start(invocation)
    await model.wait_entered()
    handle.stop("unknown-stop")
    result = await handle.outcome()
    assert result.status == "uncertain"
    assert result.effects == "unknown"
    assert "stop_acknowledged" not in [e.kind for e in result.evidence]
    assert result.elapsed_seconds < 0.5
    assert result.outputs == ()
    with pytest.raises(ValueError, match="replay"):
        host.start(invocation)
    await host.wait_local_settlement()
    assert result.effects == "unknown"  # Later local completion does not rewrite receipt.
    assert model.calls == 1


async def test_waiter_cancellation_does_not_imply_worker_stop():
    model = OfflineChatModel(delay=0.02)
    handle = OfflineHarness((binding(factory=lambda: model),)).start(spec())
    waiter = asyncio.create_task(handle.outcome())
    await model.wait_entered()
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    result = await handle.outcome()
    assert result.status == "completed"
    assert "stop_requested" not in [e.kind for e in result.evidence]


async def test_no_provider_or_reused_model_accepted():
    bad = replace(binding(), factory=lambda: "anthropic:default")
    result = await OfflineHarness((bad,)).start(spec()).outcome()
    assert result.failure == "permission_denied"
    model = OfflineChatModel()
    host = OfflineHarness((binding(factory=lambda: model),))
    assert (await host.start(spec()).outcome()).status == "completed"
    next_spec = with_agents(spec(), spec().agents, invocation_id="run-2")
    assert (await host.start(next_spec).outcome()).failure == "permission_denied"


async def test_missing_usage_is_unknown_with_supplied_price():
    result = await OfflineHarness((binding(),)).start(spec(prices=(price(),))).outcome()
    assert result.status == "completed"
    assert result.outputs[0].usage is None
    assert result.outputs[0].estimate.reason == "missing_usage"
    assert result.outputs[0].estimate.amount is None


async def test_unacknowledged_completion_within_grace_is_not_cancel_ack():
    model = OfflineChatModel(delay=0.01, acknowledge_stop=False)
    host = OfflineHarness((binding(factory=lambda: model),))
    handle = host.start(spec())
    await model.wait_entered()
    handle.stop("racing-stop")
    result = await handle.outcome()
    assert result.status == "uncertain"
    assert result.effects == "local_settled"
    assert "stop_acknowledged" not in [e.kind for e in result.evidence]
    assert result.outputs == ()
    assert model.calls == 1
    assert model.stop_acknowledged is False
    assert result.model_bindings == (binding().identity,)


async def test_handle_snapshot_cannot_be_replaced_and_unchecked_limits_revalidated():
    from pydantic import ValidationError

    original = spec()
    host = OfflineHarness((binding(),))
    handle = host.start(original)
    with pytest.raises(AttributeError):
        handle.spec = original.model_copy(update={"input_text": "changed"})
    assert handle.spec == original and handle.spec is not original
    assert (await handle.outcome()).invocation_fingerprint == original.fingerprint
    bad = original.model_copy(update={"bounds": Bounds().model_copy(update={"steps": 0})})
    with pytest.raises(ValidationError):
        host.start(bad)
