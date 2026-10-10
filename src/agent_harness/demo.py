"""Runnable offline API demonstration: python -m agent_harness.demo."""

import asyncio
from datetime import date
from decimal import Decimal
from functools import partial

from langchain_core.messages import AIMessage

from agent_harness.adapter import OfflineBinding, OfflineHarness
from agent_harness.fakes import OfflineChatModel
from agent_harness.records import Agent, Bounds, Invocation, ModelBinding, Price


def invocation(identity: str, agents: tuple[Agent, ...], **kwargs: object) -> Invocation:
    return Invocation.model_validate(
        {
            "invocation_id": identity,
            "input_id": "hello-v1",
            "configuration_id": "demo-v1",
            "input_text": "hello",
            "agents": agents,
            **kwargs,
        }
    )


def _fixture(model: OfflineChatModel) -> OfflineChatModel:
    return model


async def main() -> None:
    a = ModelBinding(provider="offline", model="a", revision="1")
    b = ModelBinding(provider="offline", model="b", revision="1")
    host = OfflineHarness(
        (
            OfflineBinding(a, lambda: OfflineChatModel(label="a")),
            OfflineBinding(b, lambda: OfflineChatModel(label="b")),
        )
    )
    one = Agent(name="one", instructions="Respond to the input", binding=a)
    for name, agents in (
        ("single", (one,)),
        ("swapped", (one.model_copy(update={"binding": b}),)),
        ("handoff", (one, Agent(name="two", instructions="Review first output", binding=b))),
    ):
        result = await host.start(invocation(name, agents)).outcome()
        assert result.status == "completed"
        print(name, result.model_dump_json())

    quoted = Price(
        binding=a,
        currency="USD",
        input_per_unit=Decimal("2"),
        output_per_unit=Decimal("6"),
        tokens_per_unit=1000000,
        source="supplied demo fixture",
        effective_date=date(2026, 10, 10),
    )
    fixture = OfflineChatModel(
        replies=(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "uppercase",
                        "args": {"text": "hello"},
                        "id": "demo-tool",
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
    result = (
        await OfflineHarness((OfflineBinding(a, lambda: fixture),))
        .start(
            invocation(
                "tool-and-estimate",
                (one.model_copy(update={"tools": ("uppercase",)}),),
                prices=(quoted,),
            )
        )
        .outcome()
    )
    assert result.status == "completed" and result.outputs[0].text == "HELLO"
    assert result.outputs[0].estimate.amount == Decimal("0.00032")
    print("tool-and-estimate", result.model_dump_json())

    rejected = await host.start(
        invocation(
            "capability-rejected",
            (one.model_copy(update={"required_capabilities": ("images",)}),),
        )
    ).outcome()
    assert rejected.status == "rejected" and rejected.steps == 0
    print("capability-rejected", rejected.model_dump_json())

    for name, acknowledge in (("cancelled", True), ("uncertain", False)):
        model = OfflineChatModel(delay=0.1, acknowledge_stop=acknowledge)
        stop_host = OfflineHarness((OfflineBinding(a, partial(_fixture, model)),))
        handle = stop_host.start(
            invocation(
                name,
                (one,),
                bounds=Bounds(stop_grace_seconds=0.01),
            )
        )
        await model.wait_entered()
        handle.stop("demo-stop")
        result = await handle.outcome()
        assert result.status == name
        print(name, result.model_dump_json())
        await stop_host.wait_local_settlement()


if __name__ == "__main__":
    asyncio.run(main())
