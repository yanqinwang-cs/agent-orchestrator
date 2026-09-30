"""Exporters for the versioned Python contract schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from orchestrator.domain.backend import (
    ArtifactEnvelope,
    BackendCapabilities,
    ControlAck,
    PreflightResult,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerEvent,
    WorkerIdentity,
    WorkerResult,
)
from orchestrator.domain.decisions import (
    DecisionAcceptancePolicy,
    DecisionDisposition,
    DecisionEngineFailure,
    DecisionEvidence,
    DecisionInferenceBinding,
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionScoreVector,
)
from orchestrator.domain.models import (
    AgentCatalog,
    AgentRunSpec,
    Artifact,
    AttemptState,
    BackendSettings,
    DecisionQuestionConfig,
    DevelopmentConfig,
    Event,
    Handoff,
    Intervention,
    OrchestratorPolicy,
    ProfileOverlayFile,
    ProjectConfig,
    ResolvedDecisionQuestion,
    ResolvedOrchestratorPolicy,
    RunSpec,
    RunState,
    WorkflowOverlayFile,
    WorkflowPreset,
)
from orchestrator.persistence.models import (
    ArtifactManifest,
    AttemptResult,
    CommandReceipt,
    ControlDelivery,
    DecisionRecord,
    InterventionRecord,
    LedgerMutation,
    OutboxAction,
    OwnerLease,
    ReservationRecord,
    StageProjection,
    StageRedirect,
    StageResult,
)

SCHEMAS: dict[str, Any] = {
    "agent-catalog-v1": AgentCatalog,
    "workflow-preset-v1": WorkflowPreset,
    "orchestrator-policy-v1": OrchestratorPolicy,
    "resolved-orchestrator-policy-v1": ResolvedOrchestratorPolicy,
    "decision-question-v1": DecisionQuestionConfig,
    "resolved-decision-question-v1": ResolvedDecisionQuestion,
    "decision-inference-binding-v1": DecisionInferenceBinding,
    "decision-request-v1": DecisionRequest,
    "decision-option-v1": DecisionOption,
    "decision-evidence-v1": DecisionEvidence,
    "decision-result-v1": DecisionResult,
    "decision-score-vector-v1": DecisionScoreVector,
    "decision-engine-failure-v1": DecisionEngineFailure,
    "decision-acceptance-policy-v1": DecisionAcceptancePolicy,
    "decision-disposition-v1": DecisionDisposition,
    "project-config-v1": ProjectConfig,
    "backend-settings-v1": BackendSettings,
    "run-spec-v1": RunSpec,
    "agent-run-spec-v1": AgentRunSpec,
    "run-state-v1": RunState,
    "attempt-state-v1": AttemptState,
    "intervention-v1": TypeAdapter(Intervention),
    "event-v1": TypeAdapter(Event),
    "worker-event-v1": TypeAdapter(WorkerEvent),
    "worker-result-v1": WorkerResult,
    "worker-identity-v1": WorkerIdentity,
    "steer-command-v1": SteerCommand,
    "control-ack-v1": ControlAck,
    "reconciliation-v1": Reconciliation,
    "shutdown-receipt-v1": ShutdownReceipt,
    "artifact-envelope-v1": ArtifactEnvelope,
    "backend-capabilities-v1": BackendCapabilities,
    "preflight-result-v1": PreflightResult,
    "artifact-v1": Artifact,
    "handoff-v1": Handoff,
    "development-config-v1": DevelopmentConfig,
    "profile-overlays-v1": ProfileOverlayFile,
    "workflow-overlays-v1": WorkflowOverlayFile,
    "ledger-mutation-v1": LedgerMutation,
    "decision-record-v1": DecisionRecord,
    "command-receipt-v1": CommandReceipt,
    "control-delivery-v1": ControlDelivery,
    "intervention-record-v1": InterventionRecord,
    "stage-projection-v1": StageProjection,
    "stage-redirect-v1": StageRedirect,
    "stage-result-v1": StageResult,
    "attempt-result-v1": AttemptResult,
    "outbox-action-v1": OutboxAction,
    "reservation-v1": ReservationRecord,
    "artifact-manifest-v1": ArtifactManifest,
    "owner-lease-v1": OwnerLease,
}


def export_schemas(directory: Path) -> tuple[Path, ...]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, schema_type in SCHEMAS.items():
        schema = (
            schema_type.model_json_schema()
            if hasattr(schema_type, "model_json_schema")
            else schema_type.json_schema()
        )
        target = directory / f"{name}.json"
        target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(target)
    return tuple(written)
