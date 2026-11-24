"""Scriptable offline DecisionEngine adapter with a controllable completion barrier."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable, Sequence

from orchestrator.domain.decisions import DecisionEngineReply, DecisionRequest

DecisionScript = DecisionEngineReply | Callable[[DecisionRequest], DecisionEngineReply]


class DecisionBarrier:
    """Deterministic async gate for tests that race inference with run changes."""

    def __init__(self) -> None:
        self.entered = asyncio.Event()
        self.release = asyncio.Event()


class FakeDecisionEngine:
    def __init__(
        self,
        scripts: Sequence[DecisionScript] = (),
        *,
        barrier: DecisionBarrier | None = None,
    ) -> None:
        self._scripts = deque(scripts)
        self.barrier = barrier
        self.requests: list[DecisionRequest] = []

    async def decide(self, request: DecisionRequest) -> DecisionEngineReply:
        self.requests.append(request)
        if self.barrier is not None:
            self.barrier.entered.set()
            await self.barrier.release.wait()
        if not self._scripts:
            raise RuntimeError("fake decision engine has no scripted response")
        script = self._scripts.popleft()
        return script(request) if callable(script) else script
