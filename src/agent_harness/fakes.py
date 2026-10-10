"""Deterministic offline chat models. Framework types stay in this adapter fixture."""

import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field, PrivateAttr


class OfflineChatModel(BaseChatModel):
    replies: tuple[AIMessage, ...] = ()
    label: str = "fake"
    delay: float = Field(default=0, ge=0, le=1)
    acknowledge_stop: bool = True
    fail: bool = False
    _calls: int = PrivateAttr(default=0)
    _active: bool = PrivateAttr(default=False)
    _stop_acknowledged: bool = PrivateAttr(default=False)
    _seen: list[list[BaseMessage]] = PrivateAttr(default_factory=list)
    _bound_tools: list[tuple[str, ...]] = PrivateAttr(default_factory=list)
    _entered: asyncio.Event = PrivateAttr(default_factory=asyncio.Event)

    @property
    def active(self) -> bool:
        return self._active

    @property
    def stop_acknowledged(self) -> bool:
        return self._stop_acknowledged

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def seen(self) -> list[list[BaseMessage]]:
        return self._seen

    @property
    def bound_tools(self) -> list[tuple[str, ...]]:
        return self._bound_tools

    async def wait_entered(self) -> None:
        await self._entered.wait()

    @property
    def _llm_type(self) -> str:
        return "harness-offline-fixture"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "OfflineChatModel":
        self._bound_tools.append(tuple(t.name if hasattr(t, "name") else t["name"] for t in tools))
        return self

    def get_num_tokens(self, text: str) -> int:
        return len(text.split())

    def _reply(self, messages: list[BaseMessage]) -> ChatResult:
        self._seen.append(list(messages))
        index = self._calls
        self._calls += 1
        if self.fail:
            raise RuntimeError("fixture failure with secret-looking payload: never export this")
        if self.replies:
            if index >= len(self.replies):
                raise RuntimeError("fixture exhausted; no fallback")
            reply = self.replies[index].model_copy(deep=True)
        else:
            reply = AIMessage(content=f"{self.label}:{messages[-1].content}")
        return ChatResult(generations=[ChatGeneration(message=reply)])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise RuntimeError("offline harness requires async execution")

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        self._active = True
        self._entered.set()
        try:
            try:
                await asyncio.sleep(self.delay)
            except asyncio.CancelledError:
                if self.acknowledge_stop:
                    self._stop_acknowledged = True
                    raise
                # Bounded fixture simulating missing cooperative acknowledgement.
                await asyncio.sleep(self.delay)
            return self._reply(messages)
        finally:
            self._active = False
