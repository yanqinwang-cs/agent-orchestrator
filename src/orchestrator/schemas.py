"""Exporters for the versioned Python contract schemas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from orchestrator.domain.backend import (
    ArtifactEnvelope,
    BackendCapabilities,
    PreflightResult,
    WorkerEvent,
    WorkerResult,
)
from orchestrator.domain.models import (
    AgentCatalog,
    AgentRunSpec,
    Artifact,
    AttemptState,
    BackendSettings,
    DevelopmentConfig,
    Event,
    Handoff,
    Intervention,
    OrchestratorPolicy,
    ProfileOverlayFile,
    ProjectConfig,
    RunSpec,
    RunState,
    WorkflowOverlayFile,
    WorkflowPreset,
)
from orchestrator.persistence.models import (
    ArtifactManifest,
    CommandReceipt,
    LedgerMutation,
    OutboxAction,
    OwnerLease,
    ReservationRecord,
    StageProjection,
)

SCHEMAS: dict[str, Any] = {
    "agent-catalog-v1": AgentCatalog,
    "workflow-preset-v1": WorkflowPreset,
    "orchestrator-policy-v1": OrchestratorPolicy,
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
    "artifact-envelope-v1": ArtifactEnvelope,
    "backend-capabilities-v1": BackendCapabilities,
    "preflight-result-v1": PreflightResult,
    "artifact-v1": Artifact,
    "handoff-v1": Handoff,
    "development-config-v1": DevelopmentConfig,
    "profile-overlays-v1": ProfileOverlayFile,
    "workflow-overlays-v1": WorkflowOverlayFile,
    "ledger-mutation-v1": LedgerMutation,
    "command-receipt-v1": CommandReceipt,
    "stage-projection-v1": StageProjection,
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
