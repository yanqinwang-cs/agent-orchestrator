"""Provider-neutral contracts for bounded semantic decisions."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

DecisionIdText = Annotated[str, StringConstraints(min_length=1, max_length=160)]
Identifier = Annotated[str, StringConstraints(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")]
Sha256 = Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]


class DecisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class DecisionConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_default=True)


class DecisionMechanism(StrEnum):
    DETERMINISTIC_POLICY = "deterministic_policy"
    NATIVE_DECISION_MODEL = "native_decision_model"
    GENERAL_LLM_READOUT = "general_llm_readout"
    GENERATIVE_STRUCTURED_OUTPUT = "generative_structured_output"


class CalibrationIdentity(DecisionContract):
    artifact_id: DecisionIdText
    revision: DecisionIdText
    content_hash: Sha256


class InferenceStateIdentity(DecisionContract):
    state_id: DecisionIdText
    revision: DecisionIdText
    content_hash: Sha256


class DecisionInferenceBinding(DecisionContract):
    """Frozen identity for one inference mechanism, without provider SDK objects."""

    schema_version: Literal[1] = 1
    mechanism: DecisionMechanism
    adapter_id: DecisionIdText | None = None
    adapter_revision: DecisionIdText | None = None
    decision_model_id: DecisionIdText | None = None
    decision_model_revision: DecisionIdText | None = None
    base_model_id: DecisionIdText | None = None
    base_model_revision: DecisionIdText | None = None
    readout_id: DecisionIdText | None = None
    readout_revision: DecisionIdText | None = None
    calibration: CalibrationIdentity | None = None
    inference_state: InferenceStateIdentity | None = None
    deterministic_policy_id: Identifier | None = None
    deterministic_policy_revision: DecisionIdText | None = None
    deterministic_rule: Literal["first_allowed"] | None = None

    @model_validator(mode="after")
    def validate_mechanism_identity(self) -> DecisionInferenceBinding:
        identity_pairs = (
            (self.adapter_id, self.adapter_revision, "adapter"),
            (self.decision_model_id, self.decision_model_revision, "decision model"),
            (self.base_model_id, self.base_model_revision, "base model"),
            (self.readout_id, self.readout_revision, "readout"),
        )
        for identity, revision, label in identity_pairs:
            if (identity is None) != (revision is None):
                raise ValueError(f"{label} identity and revision must be supplied together")
        deterministic_fields = (
            self.deterministic_policy_id,
            self.deterministic_policy_revision,
            self.deterministic_rule,
        )
        model_fields = (
            self.adapter_id,
            self.adapter_revision,
            self.decision_model_id,
            self.decision_model_revision,
            self.base_model_id,
            self.base_model_revision,
            self.readout_id,
            self.readout_revision,
            self.calibration,
            self.inference_state,
        )
        if self.mechanism == DecisionMechanism.DETERMINISTIC_POLICY:
            if not all(deterministic_fields):
                raise ValueError("deterministic policy identity and rule are required")
            if any(model_fields):
                raise ValueError("deterministic policy binding cannot contain model identity")
        elif any(deterministic_fields):
            raise ValueError("model inference binding cannot contain deterministic policy fields")

        if self.mechanism == DecisionMechanism.NATIVE_DECISION_MODEL:
            if not self.decision_model_id or not self.decision_model_revision:
                raise ValueError("native decision model identity and revision are required")
            if self.base_model_id or self.readout_id:
                raise ValueError(
                    "native decision model binding cannot contain base/readout identity"
                )
        elif self.mechanism == DecisionMechanism.GENERAL_LLM_READOUT:
            if not all(
                (
                    self.base_model_id,
                    self.base_model_revision,
                    self.readout_id,
                    self.readout_revision,
                )
            ):
                raise ValueError("general LLM readout requires base model and readout identities")
            if self.decision_model_id or self.decision_model_revision:
                raise ValueError(
                    "general LLM readout cannot contain native decision model identity"
                )
        elif self.mechanism == DecisionMechanism.GENERATIVE_STRUCTURED_OUTPUT:
            if not self.adapter_id or not self.adapter_revision:
                raise ValueError("generative structured-output adapter identity is required")
            if any((self.decision_model_id, self.readout_id)):
                raise ValueError(
                    "generative binding cannot contain decision-model or readout identity"
                )
        return self


class DecisionEvidenceRequirement(DecisionContract):
    """A narrow, authored source reference for evidence required by a question."""

    kind: Literal["run_task", "stage_output"]
    stage_id: Identifier | None = None
    output_name: Identifier | None = None
    inclusion_reason: DecisionIdText

    @model_validator(mode="after")
    def validate_source_shape(self) -> DecisionEvidenceRequirement:
        if self.kind == "run_task" and (self.stage_id or self.output_name):
            raise ValueError("run_task evidence cannot name a stage or output")
        if self.kind == "stage_output" and not (self.stage_id and self.output_name):
            raise ValueError("stage_output evidence requires stage_id and output_name")
        return self

    @property
    def source_ref(self) -> str:
        if self.kind == "run_task":
            return "run.task"
        assert self.stage_id is not None and self.output_name is not None
        return f"{self.stage_id}.{self.output_name}"


class DecisionAcceptancePolicy(DecisionContract):
    """Deterministic rules for consuming a normalized decision result."""

    schema_version: Literal[1] = 1
    policy_id: Identifier
    revision: DecisionIdText
    mode: Literal["typed_outcome", "score_threshold"]
    understood_score_semantics: tuple[DecisionIdText, ...] = ()
    required_score_semantics: DecisionIdText | None = None
    required_score_scale: DecisionIdText | None = None
    minimum_score: float | None = Field(default=None, allow_inf_nan=False)
    required_calibration: CalibrationIdentity | None = None
    on_abstention: Literal["fallback", "attention_required"] = "attention_required"
    on_engine_failure: Literal["fallback", "attention_required"] = "attention_required"
    fallback_outcome_id: Identifier | None = None

    @model_validator(mode="after")
    def validate_policy_shape(self) -> DecisionAcceptancePolicy:
        if len(self.understood_score_semantics) != len(set(self.understood_score_semantics)):
            raise ValueError("understood score semantics must be unique")
        fallback_used = self.on_abstention == "fallback" or self.on_engine_failure == "fallback"
        if fallback_used != (self.fallback_outcome_id is not None):
            raise ValueError("fallback_outcome_id is required exactly when fallback is configured")
        if self.mode == "score_threshold":
            if not all(
                (
                    self.required_score_semantics,
                    self.required_score_scale,
                    self.minimum_score is not None,
                )
            ):
                raise ValueError("score threshold policy requires semantics, scale, and threshold")
            if self.required_score_semantics not in self.understood_score_semantics:
                raise ValueError("threshold score semantics must be explicitly understood")
        elif any(
            (
                self.required_score_semantics,
                self.required_score_scale,
                self.minimum_score is not None,
            )
        ):
            raise ValueError("typed outcome policy cannot declare a score threshold")
        return self


class DecisionQuestionConfig(DecisionConfiguration):
    """Authored bounded decision configuration stored in a workflow policy."""

    schema_version: Literal[1] = 1
    question_id: Identifier
    revision: DecisionIdText
    action: Literal["redirect_select_one"] = "redirect_select_one"
    stage_id: Identifier
    question: Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
    evidence_requirements: tuple[DecisionEvidenceRequirement, ...] = Field(
        default=(), max_length=16
    )
    inference_binding: DecisionInferenceBinding
    acceptance_policy: DecisionAcceptancePolicy

    @model_validator(mode="after")
    def validate_evidence_requirements(self) -> DecisionQuestionConfig:
        refs = tuple(item.source_ref for item in self.evidence_requirements)
        if len(refs) != len(set(refs)):
            raise ValueError("decision evidence requirements must have unique source references")
        return self


class ResolvedDecisionQuestion(DecisionContract):
    """Effective, immutable decision configuration frozen into a resolved run."""

    schema_version: Literal[1] = 1
    question_id: Identifier
    revision: DecisionIdText
    action: Literal["redirect_select_one"]
    stage_id: Identifier
    question: Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
    evidence_requirements: tuple[DecisionEvidenceRequirement, ...]
    inference_binding: DecisionInferenceBinding
    acceptance_policy: DecisionAcceptancePolicy


class DecisionOption(DecisionContract):
    outcome_id: Identifier
    label: DecisionIdText


class DecisionEvidence(DecisionContract):
    source_ref: Annotated[str, StringConstraints(min_length=1, max_length=160)]
    source_revision: DecisionIdText
    content_hash: Sha256
    inclusion_reason: DecisionIdText
    order: int = Field(ge=0)
    current_run_revision: int = Field(ge=0)
    value: Annotated[str, StringConstraints(max_length=16_384)] | None = None

    @field_validator("content_hash")
    @classmethod
    def normalize_hash(cls, value: str) -> str:
        return value.lower()

    @model_validator(mode="after")
    def verify_supplied_value(self) -> DecisionEvidence:
        if self.value is not None and hashlib.sha256(self.value.encode("utf-8")).hexdigest() != (
            self.content_hash
        ):
            raise ValueError("evidence content hash does not match the supplied value")
        return self


class DecisionRequest(DecisionContract):
    """One immutable question, evidence selection, outcome set, and effective policy."""

    schema_version: Literal[1] = 1
    decision_id: UUID
    run_id: DecisionIdText
    current_run_revision: int = Field(ge=0)
    question_id: Identifier
    question_revision: DecisionIdText
    question: Annotated[str, StringConstraints(min_length=1, max_length=2_000)]
    allowed_outcomes: tuple[DecisionOption, ...] = Field(min_length=1, max_length=16)
    required_evidence_refs: tuple[DecisionIdText, ...] = Field(default=(), max_length=16)
    missing_evidence_refs: tuple[DecisionIdText, ...] = Field(default=(), max_length=16)
    evidence: tuple[DecisionEvidence, ...] = Field(default=(), max_length=16)
    inference_binding: DecisionInferenceBinding
    acceptance_policy: DecisionAcceptancePolicy
    created_at: datetime
    parent_decision_id: UUID | None = None

    @model_validator(mode="after")
    def validate_request_bounds(self) -> DecisionRequest:
        outcome_ids = tuple(item.outcome_id for item in self.allowed_outcomes)
        evidence_refs = tuple(item.source_ref for item in self.evidence)
        if len(outcome_ids) != len(set(outcome_ids)):
            raise ValueError("allowed outcome identities must be unique")
        if len(self.required_evidence_refs) != len(set(self.required_evidence_refs)):
            raise ValueError("required evidence references must be unique")
        if len(evidence_refs) != len(set(evidence_refs)):
            raise ValueError("evidence source references must be unique")
        if not set(evidence_refs) <= set(self.required_evidence_refs):
            raise ValueError("selected evidence must be declared by the bounded question")
        if tuple(item.order for item in self.evidence) != tuple(
            sorted(item.order for item in self.evidence)
        ):
            raise ValueError("evidence must preserve semantic ordering")
        if any(item.current_run_revision != self.current_run_revision for item in self.evidence):
            raise ValueError("evidence must be bound to the request run revision")
        value_bytes = sum(len((item.value or "").encode("utf-8")) for item in self.evidence)
        if value_bytes > 32_768:
            raise ValueError("selected decision evidence exceeds the 32768-byte bound")
        if not set(self.missing_evidence_refs) <= set(self.required_evidence_refs):
            raise ValueError("missing evidence must be declared as required")
        if not set(evidence_refs).isdisjoint(self.missing_evidence_refs):
            raise ValueError("an evidence reference cannot be both present and missing")
        if self.acceptance_policy.fallback_outcome_id is not None and (
            self.acceptance_policy.fallback_outcome_id not in outcome_ids
        ):
            raise ValueError("fallback outcome must be in the allowed outcome set")
        return self

    @property
    def evidence_digest(self) -> str:
        payload = [item.model_dump(mode="json") for item in self.evidence]
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class DecisionScoreEntry(DecisionContract):
    outcome_id: Identifier
    value: float = Field(allow_inf_nan=False)


class DecisionScoreVector(DecisionContract):
    semantics_id: DecisionIdText
    scale_id: DecisionIdText
    values: tuple[DecisionScoreEntry, ...] = Field(min_length=1, max_length=16)

    @model_validator(mode="after")
    def validate_unique_options(self) -> DecisionScoreVector:
        ids = tuple(item.outcome_id for item in self.values)
        if len(ids) != len(set(ids)):
            raise ValueError("score outcome identities must be unique")
        return self


class DecisionResultClass(StrEnum):
    VALID = "valid"
    MALFORMED = "malformed"
    INCOMPATIBLE = "incompatible"


class DecisionResult(DecisionContract):
    schema_version: Literal[1] = 1
    decision_id: UUID
    effective_inference: DecisionInferenceBinding
    consumed_run_revision: int = Field(ge=0)
    consumed_evidence_digest: Sha256
    result_class: DecisionResultClass = DecisionResultClass.VALID
    outcome_id: Identifier | None = None
    abstained: bool = False
    abstention_reason: DecisionIdText | None = None
    scores: DecisionScoreVector | None = None
    adapter_result_id: DecisionIdText | None = None

    @model_validator(mode="after")
    def validate_result_shape(self) -> DecisionResult:
        if self.result_class == DecisionResultClass.VALID:
            if self.abstained and (self.outcome_id is not None or self.abstention_reason is None):
                raise ValueError("abstention requires a reason and cannot include an outcome")
            if not self.abstained and not any(
                (self.outcome_id is not None, self.scores is not None)
            ):
                raise ValueError("valid result must contain an outcome, scores, or abstention")
            if not self.abstained and self.abstention_reason is not None:
                raise ValueError("abstention reason requires abstained=true")
        elif any(
            (
                self.outcome_id is not None,
                self.abstained,
                self.abstention_reason is not None,
                self.scores is not None,
            )
        ):
            raise ValueError("malformed or incompatible result cannot carry usable output")
        return self


class DecisionFailureClass(StrEnum):
    ENGINE_UNAVAILABLE = "engine_unavailable"
    ENGINE_ERROR = "engine_error"
    ENGINE_TIMEOUT = "engine_timeout"
    MISSING_EVIDENCE = "missing_evidence"
    MALFORMED_RESULT = "malformed_result"
    INCOMPATIBLE_RESULT = "incompatible_result"


class DecisionEngineFailure(DecisionContract):
    schema_version: Literal[1] = 1
    decision_id: UUID
    classification: DecisionFailureClass
    detail: Annotated[str, StringConstraints(min_length=1, max_length=500)]
    retryable: bool = False


class DecisionDispositionStatus(StrEnum):
    ACCEPTED = "accepted"
    ABSTAINED = "abstained"
    REJECTED = "rejected"
    FALLBACK = "fallback"
    ATTENTION_REQUIRED = "attention_required"


class DecisionPolicyAction(StrEnum):
    CONTINUE = "continue"
    FALLBACK = "fallback"
    ATTENTION_REQUIRED = "attention_required"


class DecisionDispositionReason(StrEnum):
    ACCEPTED_TYPED_OUTCOME = "accepted_typed_outcome"
    ACCEPTED_SCORED_OUTCOME = "accepted_scored_outcome"
    EXPLICIT_ABSTENTION = "explicit_abstention"
    SCORE_BELOW_THRESHOLD = "score_below_threshold"
    STALE_RUN_REVISION = "stale_run_revision"
    STALE_EVIDENCE = "stale_evidence"
    DISALLOWED_OUTCOME = "disallowed_outcome"
    MALFORMED_RESULT = "malformed_result"
    INCOMPATIBLE_RESULT = "incompatible_result"
    UNSUPPORTED_SCORE_SEMANTICS = "unsupported_score_semantics"
    SCORE_MAPPING_MISMATCH = "score_mapping_mismatch"
    INVALID_SCORE_VECTOR = "invalid_score_vector"
    CALIBRATION_MISMATCH = "calibration_mismatch"
    INFERENCE_IDENTITY_MISMATCH = "inference_identity_mismatch"
    ENGINE_FAILURE = "engine_failure"
    MISSING_EVIDENCE = "missing_evidence"
    OUTCOME_NO_LONGER_ALLOWED = "outcome_no_longer_allowed"


class DecisionDisposition(DecisionContract):
    schema_version: Literal[1] = 1
    decision_id: UUID
    request_hash: Sha256
    result_hash: Sha256 | None = None
    status: DecisionDispositionStatus
    policy_action: DecisionPolicyAction
    reason: DecisionDispositionReason
    policy_id: Identifier
    policy_revision: DecisionIdText
    selected_outcome_id: Identifier | None = None
    score_semantics_used: DecisionIdText | None = None
    threshold_used: float | None = Field(default=None, allow_inf_nan=False)
    resulting_run_revision: int | None = Field(default=None, ge=0)
    action_reference: DecisionIdText | None = None
    evaluated_at: datetime

    @model_validator(mode="after")
    def validate_selected_outcome(self) -> DecisionDisposition:
        if self.status in {DecisionDispositionStatus.ACCEPTED, DecisionDispositionStatus.FALLBACK}:
            if self.selected_outcome_id is None:
                raise ValueError("accepted or fallback disposition requires a selected outcome")
        elif self.selected_outcome_id is not None:
            raise ValueError("non-accepted disposition cannot select an outcome")
        if self.status == DecisionDispositionStatus.ACCEPTED and (
            self.policy_action != DecisionPolicyAction.CONTINUE
        ):
            raise ValueError("accepted disposition must continue")
        if self.status == DecisionDispositionStatus.FALLBACK and (
            self.policy_action != DecisionPolicyAction.FALLBACK
        ):
            raise ValueError("fallback disposition must use the fallback action")
        if (
            self.status
            in {
                DecisionDispositionStatus.ABSTAINED,
                DecisionDispositionStatus.REJECTED,
                DecisionDispositionStatus.ATTENTION_REQUIRED,
            }
            and self.policy_action != DecisionPolicyAction.ATTENTION_REQUIRED
        ):
            raise ValueError("non-accepted disposition must require attention")
        return self


type DecisionEngineReply = DecisionResult | DecisionEngineFailure


class DecisionEngine(Protocol):
    """One bounded inference call; implementations cannot mutate orchestration state."""

    async def decide(self, request: DecisionRequest) -> DecisionEngineReply: ...


def decision_request_hash(request: DecisionRequest) -> str:
    encoded = json.dumps(
        request.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def decision_result_hash(result: DecisionResult) -> str:
    encoded = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def evaluate_decision(
    request: DecisionRequest,
    reply: DecisionEngineReply,
    *,
    current_run_revision: int,
    currently_allowed_outcomes: set[str] | frozenset[str],
    evaluated_at: datetime,
) -> DecisionDisposition:
    """Apply the request's deterministic policy without granting action authority."""
    policy = request.acceptance_policy
    request_hash = decision_request_hash(request)
    result_hash = decision_result_hash(reply) if isinstance(reply, DecisionResult) else None

    def disposition(
        status: DecisionDispositionStatus,
        reason: DecisionDispositionReason,
        *,
        selected: str | None = None,
        score_semantics: str | None = None,
        threshold: float | None = None,
    ) -> DecisionDisposition:
        action = (
            DecisionPolicyAction.CONTINUE
            if status == DecisionDispositionStatus.ACCEPTED
            else DecisionPolicyAction.FALLBACK
            if status == DecisionDispositionStatus.FALLBACK
            else DecisionPolicyAction.ATTENTION_REQUIRED
        )
        return DecisionDisposition(
            decision_id=request.decision_id,
            request_hash=request_hash,
            result_hash=result_hash,
            status=status,
            policy_action=action,
            reason=reason,
            policy_id=policy.policy_id,
            policy_revision=policy.revision,
            selected_outcome_id=selected,
            score_semantics_used=score_semantics,
            threshold_used=threshold,
            evaluated_at=evaluated_at,
        )

    def abstain(reason: DecisionDispositionReason) -> DecisionDisposition:
        if policy.on_abstention == "fallback":
            assert policy.fallback_outcome_id is not None
            return disposition(
                DecisionDispositionStatus.FALLBACK,
                reason,
                selected=policy.fallback_outcome_id,
            )
        return disposition(DecisionDispositionStatus.ABSTAINED, reason)

    def invalid(reason: DecisionDispositionReason) -> DecisionDisposition:
        return disposition(DecisionDispositionStatus.REJECTED, reason)

    required_refs = set(request.required_evidence_refs)
    present_refs = {item.source_ref for item in request.evidence}
    if request.missing_evidence_refs or not required_refs <= present_refs:
        return disposition(
            DecisionDispositionStatus.ATTENTION_REQUIRED,
            DecisionDispositionReason.MISSING_EVIDENCE,
        )
    if current_run_revision != request.current_run_revision:
        return invalid(DecisionDispositionReason.STALE_RUN_REVISION)
    if isinstance(reply, DecisionEngineFailure):
        if reply.decision_id != request.decision_id:
            return invalid(DecisionDispositionReason.INCOMPATIBLE_RESULT)
        if reply.classification == DecisionFailureClass.MISSING_EVIDENCE:
            return disposition(
                DecisionDispositionStatus.ATTENTION_REQUIRED,
                DecisionDispositionReason.MISSING_EVIDENCE,
            )
        if policy.on_engine_failure == "fallback":
            assert policy.fallback_outcome_id is not None
            return disposition(
                DecisionDispositionStatus.FALLBACK,
                DecisionDispositionReason.ENGINE_FAILURE,
                selected=policy.fallback_outcome_id,
            )
        return disposition(
            DecisionDispositionStatus.ATTENTION_REQUIRED,
            DecisionDispositionReason.ENGINE_FAILURE,
        )

    if reply.decision_id != request.decision_id:
        return invalid(DecisionDispositionReason.INCOMPATIBLE_RESULT)
    if (
        current_run_revision != request.current_run_revision
        or reply.consumed_run_revision != request.current_run_revision
    ):
        return invalid(DecisionDispositionReason.STALE_RUN_REVISION)
    if reply.consumed_evidence_digest != request.evidence_digest:
        return invalid(DecisionDispositionReason.STALE_EVIDENCE)
    if policy.required_calibration is not None and (
        reply.effective_inference.calibration != policy.required_calibration
    ):
        return invalid(DecisionDispositionReason.CALIBRATION_MISMATCH)
    if reply.effective_inference != request.inference_binding:
        return invalid(DecisionDispositionReason.INFERENCE_IDENTITY_MISMATCH)
    if reply.result_class == DecisionResultClass.MALFORMED:
        return invalid(DecisionDispositionReason.MALFORMED_RESULT)
    if reply.result_class == DecisionResultClass.INCOMPATIBLE:
        return invalid(DecisionDispositionReason.INCOMPATIBLE_RESULT)

    requested_ids = tuple(item.outcome_id for item in request.allowed_outcomes)
    if reply.outcome_id is not None and reply.outcome_id not in requested_ids:
        return invalid(DecisionDispositionReason.DISALLOWED_OUTCOME)
    if reply.outcome_id is not None and reply.outcome_id not in currently_allowed_outcomes:
        return invalid(DecisionDispositionReason.OUTCOME_NO_LONGER_ALLOWED)

    score_semantics: str | None = None
    selected_from_scores: str | None = None
    if reply.scores is not None:
        score_semantics = reply.scores.semantics_id
        if score_semantics not in policy.understood_score_semantics:
            return invalid(DecisionDispositionReason.UNSUPPORTED_SCORE_SEMANTICS)
        score_ids = tuple(item.outcome_id for item in reply.scores.values)
        if set(score_ids) != set(requested_ids):
            return invalid(DecisionDispositionReason.SCORE_MAPPING_MISMATCH)
        score_by_outcome = {item.outcome_id: item.value for item in reply.scores.values}
        if score_semantics == "probability_distribution_v1":
            values = tuple(score_by_outcome.values())
            if (
                any(value < 0 or value > 1 for value in values)
                or abs(sum(values) - 1.0) > 1e-6
                or reply.scores.scale_id != "unit_interval"
            ):
                return invalid(DecisionDispositionReason.INVALID_SCORE_VECTOR)
        if policy.mode == "score_threshold":
            assert policy.required_score_semantics is not None
            assert policy.required_score_scale is not None
            assert policy.minimum_score is not None
            if (
                score_semantics != policy.required_score_semantics
                or reply.scores.scale_id != policy.required_score_scale
            ):
                return invalid(DecisionDispositionReason.UNSUPPORTED_SCORE_SEMANTICS)
            selected_from_scores = max(
                requested_ids,
                key=lambda outcome_id: score_by_outcome[outcome_id],
            )
            if reply.outcome_id is not None and reply.outcome_id != selected_from_scores:
                return invalid(DecisionDispositionReason.SCORE_MAPPING_MISMATCH)
            if score_by_outcome[selected_from_scores] < policy.minimum_score:
                return abstain(DecisionDispositionReason.SCORE_BELOW_THRESHOLD)
        elif reply.outcome_id is None:
            return invalid(DecisionDispositionReason.SCORE_MAPPING_MISMATCH)
    elif policy.mode == "score_threshold":
        return invalid(DecisionDispositionReason.SCORE_MAPPING_MISMATCH)

    if reply.abstained:
        return abstain(DecisionDispositionReason.EXPLICIT_ABSTENTION)

    selected = reply.outcome_id or selected_from_scores
    if selected is None:
        return invalid(DecisionDispositionReason.MALFORMED_RESULT)
    if selected not in currently_allowed_outcomes:
        return invalid(DecisionDispositionReason.OUTCOME_NO_LONGER_ALLOWED)
    return disposition(
        DecisionDispositionStatus.ACCEPTED,
        DecisionDispositionReason.ACCEPTED_SCORED_OUTCOME
        if reply.scores is not None
        else DecisionDispositionReason.ACCEPTED_TYPED_OUTCOME,
        selected=selected,
        score_semantics=score_semantics,
        threshold=policy.minimum_score if policy.mode == "score_threshold" else None,
    )
