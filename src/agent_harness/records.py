"""Versioned, framework-independent invocation records; no database or credentials."""

from datetime import date
from decimal import Decimal
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Value(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ModelBinding(Value):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    revision: str = Field(min_length=1)


class Agent(Value):
    name: str = Field(min_length=1)
    instructions: str = Field(min_length=1, max_length=10000)
    binding: ModelBinding
    tools: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ("tool_calls",)


class Bounds(Value):
    # A step is one model or tool call, shared across both agents.
    steps: int = Field(default=8, ge=1, le=100)
    seconds: float = Field(default=5, gt=0, le=60, allow_inf_nan=False)
    stop_grace_seconds: float = Field(default=0.1, gt=0, le=1, allow_inf_nan=False)


class Price(Value):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    input_per_unit: Decimal = Field(ge=0, allow_inf_nan=False)
    output_per_unit: Decimal = Field(ge=0, allow_inf_nan=False)
    tokens_per_unit: int = Field(gt=0)
    source: str = Field(min_length=1)
    effective_date: date
    binding: ModelBinding


class Invocation(Value):
    schema_version: Literal[1] = 1
    invocation_id: str = Field(min_length=1)
    input_id: str = Field(min_length=1)
    configuration_id: str = Field(min_length=1)
    input_text: str = Field(max_length=10000)
    agents: tuple[Agent, ...] = Field(min_length=1, max_length=2)
    bounds: Bounds = Bounds()
    prices: tuple[Price, ...] = ()

    @model_validator(mode="after")
    def unique_agents_and_prices(self) -> "Invocation":
        if len({a.name for a in self.agents}) != len(self.agents):
            raise ValueError("agent names must be unique")
        if len({p.binding for p in self.prices}) != len(self.prices):
            raise ValueError("one supplied price per binding")
        if any(p.binding not in {a.binding for a in self.agents} for p in self.prices):
            raise ValueError("prices must refer to declared bindings")
        return self

    @property
    def fingerprint(self) -> str:
        """Content identity, in addition to caller-supplied input/configuration identities."""
        return sha256(self.model_dump_json().encode()).hexdigest()


class Usage(Value):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)


class Estimate(Value):
    kind: Literal["estimate"] = "estimate"  # Never billed cost.
    amount: Decimal | None
    price: Price | None
    reason: Literal["known", "missing_price", "missing_usage"]


def estimate(usage: Usage | None, price: Price | None) -> Estimate:
    if price is None:
        return Estimate(amount=None, price=None, reason="missing_price")
    if usage is None or usage.input_tokens is None or usage.output_tokens is None:
        return Estimate(amount=None, price=price, reason="missing_usage")
    amount = (
        Decimal(usage.input_tokens) * price.input_per_unit
        + Decimal(usage.output_tokens) * price.output_per_unit
    ) / price.tokens_per_unit
    return Estimate(amount=amount, price=price, reason="known")


class AgentOutput(Value):
    agent: str
    binding: ModelBinding
    text: str
    usage: Usage | None
    estimate: Estimate


class Evidence(Value):
    sequence: int
    kind: Literal["started", "stop_requested", "stop_acknowledged", "terminal", "effects"]
    actor: Literal["caller", "host", "adapter"]
    request_id: str | None = None
    detail: str  # Fixed safe labels, not exception messages or provider payloads.


class Version(Value):
    component: str
    version: str


class Outcome(Value):
    schema_version: Literal[1] = 1
    invocation_id: str
    input_id: str
    configuration_id: str
    invocation_fingerprint: str
    harness: str = "deepagents-offline-v1"
    host: str = "local-asyncio"
    status: Literal[
        "completed", "rejected", "failed", "limited", "timed_out", "cancelled", "uncertain"
    ]
    failure: str | None = None
    outputs: tuple[AgentOutput, ...] = ()
    model_bindings: tuple[ModelBinding, ...] = ()
    elapsed_seconds: float = Field(ge=0)
    steps: int = Field(ge=0)
    versions: tuple[Version, ...]
    evidence: tuple[Evidence, ...]
    effects: Literal["local_settled", "not_started", "unknown"]
