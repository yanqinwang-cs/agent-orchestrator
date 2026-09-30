import asyncio
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from orchestrator.backends.decision import DeterministicDecisionEngine
from orchestrator.backends.fake_decision import DecisionBarrier, FakeDecisionEngine
from orchestrator.domain.decisions import (
    CalibrationIdentity,
    DecisionAcceptancePolicy,
    DecisionDispositionReason,
    DecisionDispositionStatus,
    DecisionEvidence,
    DecisionInferenceBinding,
    DecisionMechanism,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionResultClass,
    DecisionScoreEntry,
    DecisionScoreVector,
    evaluate_decision,
)


def _request(
    *,
    acceptance_policy: DecisionAcceptancePolicy | None = None,
    inference_binding: DecisionInferenceBinding | None = None,
) -> DecisionRequest:
    value = "Implement the bounded decision contract"
    return DecisionRequest(
        decision_id=uuid4(),
        run_id="run-1",
        current_run_revision=7,
        question_id="implementer_choice",
        question_revision="1",
        question="Choose one approved implementation specialist.",
        allowed_outcomes=(
            DecisionOption(outcome_id="prototype-implementer", label="Prototype specialist"),
            DecisionOption(outcome_id="implementer", label="General implementer"),
        ),
        required_evidence_refs=("run.task",),
        evidence=(
            DecisionEvidence(
                source_ref="run.task",
                source_revision="spec-sha256:abc",
                content_hash=sha256(value.encode()).hexdigest(),
                inclusion_reason="The implementation request defines the work being routed.",
                order=0,
                current_run_revision=7,
                value=value,
            ),
        ),
        inference_binding=inference_binding
        or DecisionInferenceBinding(
            mechanism=DecisionMechanism.DETERMINISTIC_POLICY,
            deterministic_policy_id="first_allowed_outcome",
            deterministic_policy_revision="1",
            deterministic_rule="first_allowed",
        ),
        acceptance_policy=acceptance_policy
        or DecisionAcceptancePolicy(policy_id="typed_outcome", revision="1", mode="typed_outcome"),
        created_at=datetime(2026, 9, 30, tzinfo=UTC),
    )


def test_decision_request_round_trips_immutable_bounded_contract() -> None:
    request = _request()

    restored = DecisionRequest.model_validate(request.model_dump(mode="json"))

    assert restored == request
    assert [item.outcome_id for item in restored.allowed_outcomes] == [
        "prototype-implementer",
        "implementer",
    ]
    assert (
        restored.evidence[0].content_hash
        == sha256(b"Implement the bounded decision contract").hexdigest()
    )
    with pytest.raises(ValidationError):
        request.current_run_revision = 8
    with pytest.raises(ValidationError):
        request.allowed_outcomes[0].outcome_id = "unapproved-profile"


def test_typed_scoreless_allowed_outcome_is_accepted_deterministically() -> None:
    request = _request()
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=request.current_run_revision,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.ACCEPTED
    assert disposition.selected_outcome_id == "implementer"
    assert disposition.score_semantics_used is None


def test_probability_policy_accepts_only_a_complete_supported_distribution() -> None:
    policy = DecisionAcceptancePolicy(
        policy_id="probability-threshold",
        revision="2",
        mode="score_threshold",
        understood_score_semantics=("probability_distribution_v1",),
        required_score_semantics="probability_distribution_v1",
        required_score_scale="unit_interval",
        minimum_score=0.7,
    )
    request = _request(acceptance_policy=policy)
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        scores=DecisionScoreVector(
            semantics_id="probability_distribution_v1",
            scale_id="unit_interval",
            values=(
                DecisionScoreEntry(outcome_id="prototype-implementer", value=0.8),
                DecisionScoreEntry(outcome_id="implementer", value=0.2),
            ),
        ),
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.ACCEPTED
    assert disposition.selected_outcome_id == "prototype-implementer"
    assert disposition.score_semantics_used == "probability_distribution_v1"
    assert disposition.threshold_used == 0.7


def test_unknown_score_semantics_are_rejected_even_with_a_valid_typed_outcome() -> None:
    request = _request()
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
        scores=DecisionScoreVector(
            semantics_id="provider_magic_v9",
            scale_id="opaque",
            values=(
                DecisionScoreEntry(outcome_id="prototype-implementer", value=9),
                DecisionScoreEntry(outcome_id="implementer", value=1),
            ),
        ),
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.REJECTED
    assert disposition.reason == DecisionDispositionReason.UNSUPPORTED_SCORE_SEMANTICS


def test_score_below_threshold_uses_only_the_configured_fallback() -> None:
    policy = DecisionAcceptancePolicy(
        policy_id="probability-fallback",
        revision="1",
        mode="score_threshold",
        understood_score_semantics=("probability_distribution_v1",),
        required_score_semantics="probability_distribution_v1",
        required_score_scale="unit_interval",
        minimum_score=0.7,
        on_abstention="fallback",
        fallback_outcome_id="implementer",
    )
    request = _request(acceptance_policy=policy)
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=request.current_run_revision,
        consumed_evidence_digest=request.evidence_digest,
        scores=DecisionScoreVector(
            semantics_id="probability_distribution_v1",
            scale_id="unit_interval",
            values=(
                DecisionScoreEntry(outcome_id="prototype-implementer", value=0.55),
                DecisionScoreEntry(outcome_id="implementer", value=0.45),
            ),
        ),
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=request.current_run_revision,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.FALLBACK
    assert disposition.selected_outcome_id == "implementer"
    assert disposition.reason == DecisionDispositionReason.SCORE_BELOW_THRESHOLD


def test_calibration_and_inference_state_mismatches_are_rejected() -> None:
    expected_calibration = CalibrationIdentity(
        artifact_id="specialist-calibration",
        revision="3",
        content_hash="a" * 64,
    )
    actual_calibration = CalibrationIdentity(
        artifact_id="specialist-calibration",
        revision="4",
        content_hash="b" * 64,
    )
    readout_binding = DecisionInferenceBinding(
        mechanism=DecisionMechanism.GENERAL_LLM_READOUT,
        base_model_id="fixture-model",
        base_model_revision="1",
        readout_id="specialist-readout",
        readout_revision="2",
        calibration=actual_calibration,
    )
    policy = DecisionAcceptancePolicy(
        policy_id="calibrated-readout",
        revision="1",
        mode="typed_outcome",
        required_calibration=expected_calibration,
    )
    request = _request(acceptance_policy=policy, inference_binding=readout_binding)
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=readout_binding,
        consumed_run_revision=request.current_run_revision,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
    )
    calibration_mismatch = evaluate_decision(
        request,
        result,
        current_run_revision=request.current_run_revision,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    native_binding = DecisionInferenceBinding(
        mechanism=DecisionMechanism.NATIVE_DECISION_MODEL,
        decision_model_id="local-router",
        decision_model_revision="1",
        inference_state={"state_id": "router", "revision": "1", "content_hash": "c" * 64},
    )
    native_request = _request(inference_binding=native_binding)
    mismatched_state = DecisionInferenceBinding(
        mechanism=DecisionMechanism.NATIVE_DECISION_MODEL,
        decision_model_id="local-router",
        decision_model_revision="1",
        inference_state={"state_id": "router", "revision": "2", "content_hash": "d" * 64},
    )
    native_result = DecisionResult(
        decision_id=native_request.decision_id,
        effective_inference=mismatched_state,
        consumed_run_revision=native_request.current_run_revision,
        consumed_evidence_digest=native_request.evidence_digest,
        outcome_id="implementer",
    )
    inference_mismatch = evaluate_decision(
        native_request,
        native_result,
        current_run_revision=native_request.current_run_revision,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert calibration_mismatch.reason == DecisionDispositionReason.CALIBRATION_MISMATCH
    assert inference_mismatch.reason == DecisionDispositionReason.INFERENCE_IDENTITY_MISMATCH


def test_result_with_obsolete_evidence_revision_is_rejected() -> None:
    request = _request()
    obsolete_result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=request.current_run_revision,
        consumed_evidence_digest="f" * 64,
        outcome_id="implementer",
    )

    disposition = evaluate_decision(
        request,
        obsolete_result,
        current_run_revision=request.current_run_revision,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.REJECTED
    assert disposition.reason == DecisionDispositionReason.STALE_EVIDENCE


def test_stale_run_and_evidence_revisions_fail_closed() -> None:
    request = _request()
    stale_run_result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
    )
    stale_evidence_result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest="f" * 64,
        outcome_id="implementer",
    )

    stale_run = evaluate_decision(
        request,
        stale_run_result,
        current_run_revision=8,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )
    stale_evidence = evaluate_decision(
        request,
        stale_evidence_result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert stale_run.reason == DecisionDispositionReason.STALE_RUN_REVISION
    assert stale_evidence.reason == DecisionDispositionReason.STALE_EVIDENCE
    assert stale_run.status == stale_evidence.status == DecisionDispositionStatus.REJECTED


def test_allowed_outcome_that_left_current_policy_is_rejected() -> None:
    request = _request()
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.reason == DecisionDispositionReason.OUTCOME_NO_LONGER_ALLOWED
    assert disposition.status == DecisionDispositionStatus.REJECTED


def test_explicit_abstention_uses_only_the_declared_fallback() -> None:
    request = _request(
        acceptance_policy=DecisionAcceptancePolicy(
            policy_id="typed-with-fallback",
            revision="1",
            mode="typed_outcome",
            on_abstention="fallback",
            fallback_outcome_id="prototype-implementer",
        )
    )
    result = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        abstained=True,
        abstention_reason="The evidence does not distinguish the two candidates.",
    )

    disposition = evaluate_decision(
        request,
        result,
        current_run_revision=7,
        currently_allowed_outcomes={"prototype-implementer", "implementer"},
        evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
    )

    assert disposition.status == DecisionDispositionStatus.FALLBACK
    assert disposition.selected_outcome_id == "prototype-implementer"
    assert disposition.reason == DecisionDispositionReason.EXPLICIT_ABSTENTION


def test_malformed_and_disallowed_results_never_become_accepted() -> None:
    request = _request()
    malformed = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        result_class=DecisionResultClass.MALFORMED,
    )
    disallowed = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="reviewer",
    )

    outcomes = [
        evaluate_decision(
            request,
            result,
            current_run_revision=7,
            currently_allowed_outcomes={"prototype-implementer", "implementer"},
            evaluated_at=datetime(2026, 9, 30, tzinfo=UTC),
        )
        for result in (malformed, disallowed)
    ]

    assert [item.reason for item in outcomes] == [
        DecisionDispositionReason.MALFORMED_RESULT,
        DecisionDispositionReason.DISALLOWED_OUTCOME,
    ]
    assert all(item.policy_action.value == "attention_required" for item in outcomes)


def test_four_inference_shapes_have_distinct_effective_identity() -> None:
    calibration = {"artifact_id": "reviewer-calibration", "revision": "3", "content_hash": "a" * 64}
    shapes = (
        DecisionInferenceBinding(
            mechanism=DecisionMechanism.DETERMINISTIC_POLICY,
            deterministic_policy_id="first_allowed_outcome",
            deterministic_policy_revision="1",
            deterministic_rule="first_allowed",
        ),
        DecisionInferenceBinding(
            mechanism=DecisionMechanism.NATIVE_DECISION_MODEL,
            decision_model_id="local-specialist-router",
            decision_model_revision="2",
            inference_state={
                "state_id": "router-weights",
                "revision": "4",
                "content_hash": "b" * 64,
            },
        ),
        DecisionInferenceBinding(
            mechanism=DecisionMechanism.GENERAL_LLM_READOUT,
            base_model_id="fixture-general-model",
            base_model_revision="2026-09",
            readout_id="specialist-readout",
            readout_revision="5",
            calibration=calibration,
        ),
        DecisionInferenceBinding(
            mechanism=DecisionMechanism.GENERATIVE_STRUCTURED_OUTPUT,
            adapter_id="offline-structured-output-fixture",
            adapter_revision="1",
        ),
    )

    restored = tuple(
        DecisionInferenceBinding.model_validate(item.model_dump(mode="json")) for item in shapes
    )

    assert restored == shapes
    assert restored[0].base_model_id is None
    assert restored[1].decision_model_id == "local-specialist-router"
    assert restored[2].calibration is not None
    assert restored[3].base_model_id is None


def test_four_offline_result_fixtures_normalize_to_one_decision_contract() -> None:
    fixture_root = Path(__file__).parent / "fixtures" / "decisions"
    fixture_names = (
        "deterministic-policy",
        "native-decision-model",
        "general-llm-readout",
        "generative-structured-output",
    )

    results = tuple(
        DecisionResult.model_validate_json((fixture_root / f"{name}.json").read_text())
        for name in fixture_names
    )

    assert len(results) == 4
    assert {item.effective_inference.mechanism for item in results} == set(DecisionMechanism)
    assert all(item.decision_id == results[0].decision_id for item in results)
    assert all(item.consumed_run_revision == 4 for item in results)
    assert results[1].scores is not None
    assert results[1].scores.semantics_id == "probability_distribution_v1"
    assert results[2].effective_inference.calibration is not None
    assert results[3].scores is None


def test_model_free_decision_engine_is_repeatable_and_uses_declared_order() -> None:
    request = _request()
    engine = DeterministicDecisionEngine()

    first = asyncio.run(engine.decide(request))
    second = asyncio.run(engine.decide(request))

    assert first == second
    assert isinstance(first, DecisionResult)
    assert first.outcome_id == "prototype-implementer"
    assert first.effective_inference == request.inference_binding


def test_fake_decision_engine_has_a_deterministic_async_barrier() -> None:
    request = _request()
    response = DecisionResult(
        decision_id=request.decision_id,
        effective_inference=request.inference_binding,
        consumed_run_revision=7,
        consumed_evidence_digest=request.evidence_digest,
        outcome_id="implementer",
    )
    barrier = DecisionBarrier()
    engine = FakeDecisionEngine((response,), barrier=barrier)

    async def exercise() -> DecisionResult:
        task = asyncio.create_task(engine.decide(request))
        await barrier.entered.wait()
        assert not task.done()
        barrier.release.set()
        reply = await task
        assert isinstance(reply, DecisionResult)
        return reply

    assert asyncio.run(exercise()) == response
    assert engine.requests == [request]
