"""Offline-only Deep Agents adapter. LangGraph owns all agent/tool scheduling."""

import asyncio
import platform
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from importlib.metadata import version
from typing import Any, Literal, TypedDict
from uuid import uuid4

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context

from agent_harness.fakes import OfflineChatModel
from agent_harness.records import (
    AgentOutput,
    Evidence,
    Invocation,
    ModelBinding,
    Outcome,
    Usage,
    Version,
    estimate,
)


@tool
async def uppercase(text: str) -> str:
    """Uppercase fixture text without I/O or external effects."""
    return text.upper()


class StepLimit(Exception):
    pass


class PermissionDenied(Exception):
    pass


@dataclass(frozen=True)
class OfflineBinding:
    identity: ModelBinding
    factory: Callable[[], OfflineChatModel]
    capabilities: frozenset[str] = frozenset({"tool_calls"})


@dataclass
class _Execution:
    spec: Invocation
    steps: int = 0
    outputs: list[AgentOutput] = field(default_factory=list)
    bindings: list[ModelBinding] = field(default_factory=list)
    models: list[OfflineChatModel] = field(default_factory=list)

    def step(self) -> None:
        if self.steps >= self.spec.bounds.steps:
            raise StepLimit
        self.steps += 1


class _Guard(AgentMiddleware):
    def __init__(self, execution: _Execution, allowed: tuple[str, ...]) -> None:
        self.execution = execution
        self.allowed = allowed

    async def awrap_model_call(self, request: Any, handler: Any) -> Any:
        self.execution.step()
        # Deep Agents adds filesystem, shell, todo and subagent tools by default.
        # Remove them from the model schema AND deny them at execution below.
        tools = [
            t
            for t in request.tools
            if (t.name if hasattr(t, "name") else t.get("name")) in self.allowed
        ]
        return await handler(request.override(tools=tools))

    async def awrap_tool_call(self, request: Any, handler: Any) -> Any:
        if request.tool_call["name"] not in self.allowed:
            raise PermissionDenied
        self.execution.step()
        return await handler(request)


class _State(TypedDict):
    text: str


class Handle:
    """One invocation; a stop request is not an acknowledgement or settled effects."""

    def __init__(self, adapter: "OfflineHarness", spec: Invocation) -> None:
        self._spec = spec
        self._stop = asyncio.Event()
        self._request_id: str | None = None
        self._task = asyncio.create_task(adapter._run(self))

    @property
    def spec(self) -> Invocation:
        return self._spec

    def stop(self, request_id: str | None = None) -> str | None:
        if self._task.done():
            return None  # Already terminal; don't invent a stop acknowledgement.
        if self._request_id is None:
            self._request_id = request_id or str(uuid4())
            self._stop.set()
        return self._request_id

    async def outcome(self) -> Outcome:
        # Cancellation of a waiter cannot silently cancel or replay the invocation.
        return await asyncio.shield(self._task)


class OfflineHarness:
    """An in-process offline fixture host, not a sandbox for arbitrary injected code."""

    def __init__(self, bindings: tuple[OfflineBinding, ...]) -> None:
        self._bindings = {b.identity: b for b in bindings}
        if len(self._bindings) != len(bindings):
            raise ValueError("duplicate binding")
        self._ids: set[str] = set()
        self._models: list[OfflineChatModel] = []
        self._unsettled: set[asyncio.Task[Any]] = set()

    def start(self, spec: Invocation) -> Handle:
        # Revalidate copies made with Pydantic's unchecked model_copy(update=...).
        spec = Invocation.model_validate_json(spec.model_dump_json())
        if spec.invocation_id in self._ids:
            raise ValueError("invocation identity already used; automatic replay is forbidden")
        self._ids.add(spec.invocation_id)
        return Handle(self, spec)

    def _preflight(self, spec: Invocation) -> str | None:
        for agent in spec.agents:
            binding = self._bindings.get(agent.binding)
            if binding is None:
                return "unknown_binding"
            if not set(agent.required_capabilities).union({"tool_calls"}) <= binding.capabilities:
                return "unsupported_capability"
            if len(set(agent.tools)) != len(agent.tools) or set(agent.tools) - {"uppercase"}:
                return "undeclared_or_unavailable_tool"
        return None

    async def _invoke(self, execution: _Execution) -> None:
        spec = execution.spec
        graph = StateGraph(_State)
        previous = START
        for index, agent in enumerate(spec.agents):
            model = self._bindings[agent.binding].factory()
            if not isinstance(model, OfflineChatModel):
                raise PermissionDenied  # No provider strings or implicit model resolution.
            if any(model is old for old in self._models):
                raise PermissionDenied  # Each agent gets a fresh, independent model instance.
            self._models.append(model)
            execution.bindings.append(agent.binding)
            execution.models.append(model)
            deep_agent = create_deep_agent(
                model=model,
                system_prompt=agent.instructions,
                tools=[uppercase] if "uppercase" in agent.tools else [],
                middleware=[_Guard(execution, agent.tools)],
                backend=StateBackend,
                name=agent.name,
            )

            async def node(
                state: _State, agent: Any = agent, deep_agent: Any = deep_agent
            ) -> _State:
                result = await deep_agent.ainvoke(
                    {"messages": [HumanMessage(content=state["text"])]},
                    {"recursion_limit": spec.bounds.steps * 4 + 4},
                )
                messages = [m for m in result["messages"] if isinstance(m, AIMessage)]
                if not messages or messages[-1].tool_calls:
                    raise RuntimeError("no final output")
                usage = None
                metadata = [m.usage_metadata for m in messages if m.usage_metadata is not None]
                if len(metadata) == len(messages):
                    usage = Usage(
                        input_tokens=sum(m["input_tokens"] for m in metadata),
                        output_tokens=sum(m["output_tokens"] for m in metadata),
                    )
                price = next((p for p in spec.prices if p.binding == agent.binding), None)
                text = messages[-1].text
                execution.outputs.append(
                    AgentOutput(
                        agent=agent.name,
                        binding=agent.binding,
                        text=text,
                        usage=usage,
                        estimate=estimate(usage, price),
                    )
                )
                return {"text": text}

            name = f"agent_{index}"
            graph.add_node(name, node)
            graph.add_edge(previous, name)
            previous = name
        graph.add_edge(previous, END)
        # Fixed one- or two-node topology; no dynamic spawning, loops or custom scheduler.
        with tracing_context(enabled=False):
            await graph.compile().ainvoke(
                {"text": spec.input_text}, {"recursion_limit": len(spec.agents) + 2}
            )

    async def _run(self, handle: Handle) -> Outcome:
        start = time.monotonic()
        spec = handle.spec
        execution = _Execution(spec)
        evidence: list[Evidence] = []

        def record(kind: Any, actor: Any, detail: str, request_id: str | None = None) -> None:
            evidence.append(
                Evidence(
                    sequence=len(evidence) + 1,
                    kind=kind,
                    actor=actor,
                    detail=detail,
                    request_id=request_id,
                )
            )

        failure = self._preflight(spec)
        status: Any = "rejected"
        effects: Literal["local_settled", "not_started", "unknown"] = "not_started"
        if failure is None:
            record("started", "adapter", "offline_graph_started")
            worker = asyncio.create_task(self._invoke(execution))
            stopper = asyncio.create_task(handle._stop.wait())
            done, _ = await asyncio.wait(
                {worker, stopper},
                timeout=spec.bounds.seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if worker in done:
                if handle._request_id is not None:
                    record("stop_requested", "caller", "cancel", handle._request_id)
                effects = "local_settled"
                try:
                    worker.result()
                    status = "completed"
                except (StepLimit, GraphRecursionError):
                    status, failure = "limited", "step_limit"
                except PermissionDenied:
                    status, failure = "failed", "permission_denied"
                except Exception:
                    status, failure = "failed", "adapter_failure"
            else:
                timed_out = not handle._stop.is_set()
                request_id = handle._request_id or str(uuid4())
                record(
                    "stop_requested",
                    "host" if timed_out else "caller",
                    "deadline" if timed_out else "cancel",
                    request_id,
                )
                active_models = [m for m in execution.models if m.active]
                worker.cancel()
                settled, _ = await asyncio.wait({worker}, timeout=spec.bounds.stop_grace_seconds)
                if worker in settled:
                    # Completion during stop is local settlement, not a cancellation ack.
                    effects = "local_settled"
                    if worker.cancelled() and all(m.stop_acknowledged for m in active_models):
                        record("stop_acknowledged", "adapter", "cooperative_cancel", request_id)
                        status = "timed_out" if timed_out else "cancelled"
                    else:
                        # Graph cancellation alone is not an active model's acknowledgement.
                        if not worker.cancelled():
                            worker.exception()
                        status, failure = "uncertain", "stop_not_acknowledged"
                else:
                    status, failure, effects = "uncertain", "stop_not_acknowledged", "unknown"
                    self._unsettled.add(worker)
                    worker.add_done_callback(self._consume_unsettled)
            stopper.cancel()
            await asyncio.gather(stopper, return_exceptions=True)
        if handle._request_id is not None and not any(e.kind == "stop_requested" for e in evidence):
            record("stop_requested", "caller", "cancel", handle._request_id)
        record("terminal", "host", status)
        record("effects", "adapter", effects)
        return Outcome(
            invocation_id=spec.invocation_id,
            input_id=spec.input_id,
            configuration_id=spec.configuration_id,
            invocation_fingerprint=spec.fingerprint,
            status=status,
            failure=failure,
            outputs=tuple(execution.outputs),
            model_bindings=tuple(execution.bindings),
            elapsed_seconds=time.monotonic() - start,
            steps=execution.steps,
            versions=(
                Version(component="python", version=platform.python_version()),
                *(
                    Version(component=p, version=version(p))
                    for p in (
                        "deepagents",
                        "langchain",
                        "langchain-core",
                        "langgraph",
                        "langgraph-prebuilt",
                    )
                ),
            ),
            evidence=tuple(evidence),
            effects=effects,
        )

    def _consume_unsettled(self, task: asyncio.Task[Any]) -> None:
        self._unsettled.discard(task)
        if not task.cancelled():
            task.exception()

    async def wait_local_settlement(self) -> None:
        """Fixture cleanup only; does not amend an uncertain receipt or prove remote cleanup."""
        if self._unsettled:
            await asyncio.gather(*self._unsettled, return_exceptions=True)
