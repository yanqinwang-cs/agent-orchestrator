"""Offline decision-engine adapters."""

from __future__ import annotations

from orchestrator.domain.decisions import (
    DecisionEngineFailure,
    DecisionFailureClass,
    DecisionMechanism,
    DecisionRequest,
    DecisionResult,
)


class DeterministicDecisionEngine:
    """Resolve the configured first-allowed rule without model or network access."""

    async def decide(self, request: DecisionRequest) -> DecisionResult | DecisionEngineFailure:
        binding = request.inference_binding
        if binding.mechanism != DecisionMechanism.DETERMINISTIC_POLICY:
            return DecisionEngineFailure(
                decision_id=request.decision_id,
                classification=DecisionFailureClass.ENGINE_UNAVAILABLE,
                detail="deterministic engine cannot satisfy the configured inference mechanism",
            )
        if request.missing_evidence_refs or not set(request.required_evidence_refs) <= {
            item.source_ref for item in request.evidence
        }:
            return DecisionEngineFailure(
                decision_id=request.decision_id,
                classification=DecisionFailureClass.MISSING_EVIDENCE,
                detail="required decision evidence is missing",
            )
        return DecisionResult(
            decision_id=request.decision_id,
            effective_inference=binding,
            consumed_run_revision=request.current_run_revision,
            consumed_evidence_digest=request.evidence_digest,
            outcome_id=request.allowed_outcomes[0].outcome_id,
            adapter_result_id=(
                f"{binding.deterministic_policy_id}:{binding.deterministic_policy_revision}"
            ),
        )
