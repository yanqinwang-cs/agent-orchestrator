from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from agent_harness.records import (
    Agent,
    Bounds,
    Invocation,
    ModelBinding,
    Price,
    Usage,
    estimate,
)

BINDING = ModelBinding(provider="offline", model="a", revision="1")


def spec(**kwargs):
    return Invocation(
        invocation_id="run-1",
        input_id="input-v1",
        configuration_id="config-v1",
        input_text="hello",
        agents=(Agent(name="one", instructions="Respond", binding=BINDING),),
        **kwargs,
    )


def price(**kwargs):
    return Price(
        currency="USD",
        input_per_unit=Decimal("2"),
        output_per_unit=Decimal("6"),
        tokens_per_unit=1000000,
        source="supplied fixture",
        effective_date=date(2026, 10, 10),
        binding=BINDING,
        **kwargs,
    )


def test_immutable_versioned_round_trip_and_identity():
    original = spec()
    assert Invocation.model_validate_json(original.model_dump_json()) == original
    with pytest.raises(ValidationError):
        original.input_text = "changed"
    with pytest.raises(ValidationError):
        original.agents[0].instructions = "changed"
    assert (
        original.model_copy(update={"input_text": "different"}).fingerprint != original.fingerprint
    )
    assert original.schema_version == 1
    with pytest.raises(ValidationError):
        Invocation.model_validate({**original.model_dump(), "credentials": "not permitted"})
    with pytest.raises(ValidationError):
        Invocation.model_validate({**original.model_dump(), "schema_version": 2})


def test_limits_topology_and_price_validation():
    for values in ({"steps": 0}, {"seconds": 0}, {"seconds": float("nan")}):
        with pytest.raises(ValidationError):
            Bounds(**values)
    original = spec()
    with pytest.raises(ValidationError):
        Invocation.model_validate({**original.model_dump(), "agents": original.agents * 3})
    with pytest.raises(ValidationError):
        spec(prices=(price(), price()))
    with pytest.raises(ValidationError):
        Price.model_validate({**price().model_dump(), "input_per_unit": "-1"})


def test_estimates_keep_unknown_distinct_from_zero_and_never_claim_billing():
    known = estimate(Usage(input_tokens=100, output_tokens=20), price())
    assert known.amount == Decimal("0.00032")
    assert known.kind == "estimate"
    assert known.price.source == "supplied fixture"
    assert known.price.effective_date == date(2026, 10, 10)
    assert estimate(Usage(input_tokens=0, output_tokens=0), price()).amount == 0
    assert estimate(Usage(input_tokens=100, output_tokens=20), None).reason == "missing_price"
    for usage in (None, Usage(), Usage(input_tokens=0), Usage(output_tokens=0)):
        unknown = estimate(usage, price())
        assert unknown.amount is None
        assert unknown.reason == "missing_usage"


def test_v1_fixture_round_trip(repo_root):
    fixture = repo_root / "tests/fixtures/harness/invocation-v1.json"
    value = Invocation.model_validate_json(fixture.read_text())
    assert value.invocation_id == "fixture-run-1"
    assert value.agents[0].tools == ("uppercase",)
    assert value.prices[0].input_per_unit == Decimal("2")
    assert Invocation.model_validate_json(value.model_dump_json()) == value
