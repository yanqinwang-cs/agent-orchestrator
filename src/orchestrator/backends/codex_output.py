"""Bounded read-only Codex report bridge with locally computed artifact hashes."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import NAMESPACE_URL, uuid5

from pydantic import Field

from orchestrator.artifacts import ArtifactStore
from orchestrator.domain.backend import ArtifactEntry, OutputStatus, WorkerResult
from orchestrator.domain.models import AgentRunSpec, FrozenModel, NonEmpty
from orchestrator.persistence.ledger import SQLiteLedger, canonical_json, content_hash
from orchestrator.persistence.models import ArtifactPublication

MAX_CODEX_REPORT_BYTES = 64 * 1024
CODEX_REPORT_SCHEMA = "codex-read-only-result-v1"


class CodexReadOnlyReport(FrozenModel):
    """The only Codex output body accepted by the M6 read-only bridge."""

    schema_version: Literal[1]
    status: Literal["pass", "fail", "blocked"]
    summary: NonEmpty
    findings: tuple[NonEmpty, ...] = Field(default_factory=tuple)


def retain_read_only_report(
    raw_output: bytes,
    spec: AgentRunSpec,
    ledger: SQLiteLedger,
    artifact_store: ArtifactStore,
    *,
    observed_at: datetime | None = None,
) -> WorkerResult:
    """Validate bounded output, retain its exact bytes, and return a normalized envelope."""

    retained_bytes = raw_output[:MAX_CODEX_REPORT_BYTES]
    input_revision = content_hash(canonical_json(spec.input_manifest))
    output_hash = sha256(retained_bytes).hexdigest()
    artifact_id = str(uuid5(NAMESPACE_URL, f"codex-report:{spec.attempt_id}:{output_hash}"))
    run = ledger.get_run(spec.run_id)
    manifest = artifact_store.publish(
        ArtifactPublication(
            command_id=uuid5(NAMESPACE_URL, f"codex-report-publication:{artifact_id}"),
            expected_run_revision=run.state.revision,
            actor="codex-backend",
            run_id=spec.run_id,
            attempt_id=spec.attempt_id,
            artifact_id=artifact_id,
            input_revision=input_revision,
            workspace_revision=spec.workspace_revision,
            schema_id=CODEX_REPORT_SCHEMA,
            occurred_at=observed_at or datetime.now(UTC),
        ),
        retained_bytes,
    )
    if manifest.artifact.content_hash != output_hash:
        raise ValueError("artifact store hash does not match the retained Codex output bytes")
    if len(raw_output) > MAX_CODEX_REPORT_BYTES:
        raise ValueError(
            f"Codex report exceeds the {MAX_CODEX_REPORT_BYTES}-byte limit; bounded bytes retained"
        )
    try:
        body = CodexReadOnlyReport.model_validate_json(retained_bytes)
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("Codex output does not match codex-read-only-result-v1") from error
    return WorkerResult(
        attempt_id=spec.attempt_id,
        input_revision=input_revision,
        workspace_revision=spec.workspace_revision,
        status=OutputStatus(body.status),
        summary=body.summary,
        artifacts=(
            ArtifactEntry(
                name="report",
                schema_id=CODEX_REPORT_SCHEMA,
                content_hash=manifest.artifact.content_hash,
                relative_path=manifest.artifact.relative_path,
            ),
        ),
    )
