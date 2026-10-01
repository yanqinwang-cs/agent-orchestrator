from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from orchestrator.artifacts import ArtifactStore
from orchestrator.backends.codex import CodexBackend
from orchestrator.domain.backend import (
    PreflightContext,
    WorkerFailureEvent,
    WorkerIdentity,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    ApprovalMode,
    AttemptState,
    AttemptStatus,
    BackendPreflightRecordedEvent,
    CodexBackendSettings,
    Effort,
    EventKind,
    ModelBindingSettings,
    PermissionSet,
    SandboxMode,
)
from orchestrator.persistence import SQLiteLedger
from orchestrator.persistence.ledger import canonical_json, content_hash
from orchestrator.persistence.models import (
    AttemptRegistration,
    BackendPreflightRecord,
    LedgerMutation,
)
from orchestrator.resolution import resolve_run

pytestmark = pytest.mark.live


def _settings() -> CodexBackendSettings:
    return CodexBackendSettings(
        kind="codex_sdk",
        sdk_package="openai-codex",
        sdk_version="0.159.2",
        cli_source="sdk_pinned_dependency",
        client_per_attempt=True,
        auth_owner="codex",
        codex_home_env="ORCHESTRATOR_CODEX_HOME",
        approval_mode=ApprovalMode.DENY_ALL,
        experimental_api=False,
        interrupt_grace_seconds=5,
        shutdown_grace_seconds=5,
        allow_unverified_policy=False,
    )


def _spec(run_id: str, attempt_id: str, snapshot_hash: str, model_id: str, effort: Effort):
    return AgentRunSpec(
        run_id=run_id,
        attempt_id=attempt_id,
        profile_id="reviewer",
        profile_version="1.0.0",
        instructions=(
            "Return a concise JSON report with schema_version 1, status pass, "
            'summary "live smoke completed", and findings as an empty array. Read only.'
        ),
        input_manifest=(),
        backend="codex",
        model_id=model_id,
        effort=effort,
        permissions=PermissionSet(
            sandbox=SandboxMode.READ_ONLY,
            shell_network=False,
            web_search=False,
            approval_mode=ApprovalMode.DENY_ALL,
            external_integrations=False,
            nested_agents=False,
        ),
        skills=(),
        tools=("read_files",),
        run_snapshot_hash=snapshot_hash,
    )


def _persist_preflight(ledger, spec, preflight, context, occurred_at):
    assert preflight.snapshot is not None and preflight.prepared_handle is not None
    record = BackendPreflightRecord(
        record_id=context.record_id,
        run_id=spec.run_id,
        attempt_id=spec.attempt_id,
        preparation_id=context.preparation_id,
        attempt_spec_hash=content_hash(canonical_json(spec)),
        accepted=True,
        occurred_at=occurred_at,
        snapshot=preflight.snapshot,
        record_hash="0" * 64,
    )
    record = record.model_copy(
        update={
            "record_hash": content_hash(
                canonical_json(record.model_dump(mode="json", exclude={"record_hash"}))
            )
        }
    )
    attempt = ledger.get_attempt(spec.attempt_id)
    run = ledger.get_run(spec.run_id)
    linked_state = attempt.state.model_copy(
        update={
            "backend_preflight_record_id": record.record_id,
            "backend_preflight_record_hash": record.record_hash,
            "worker_handle_id": preflight.prepared_handle.handle_id,
            "worker_backend_version": preflight.prepared_handle.backend_version,
            "worker_thread_id": preflight.prepared_handle.thread_id,
            "worker_lifecycle_owner_id": preflight.prepared_handle.lifecycle_owner_id,
        }
    )
    event = BackendPreflightRecordedEvent(
        event_id=uuid4(),
        run_id=spec.run_id,
        occurred_at=occurred_at,
        actor="codex-live-test",
        kind=EventKind.BACKEND_PREFLIGHT_RECORDED,
        record_id=record.record_id,
        attempt_id=record.attempt_id,
        preparation_id=record.preparation_id,
        record_hash=record.record_hash,
        accepted=True,
    )
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id=spec.run_id,
            expected_revision=run.state.revision,
            actor="codex-live-test",
            occurred_at=occurred_at,
            attempt_updates=(linked_state,),
            backend_preflight_records=(record,),
            events=(event,),
        )
    )
    return record.record_id, record.record_hash


def _live_settings() -> tuple[Path, str, Effort]:
    if os.environ.get("ORCHESTRATOR_CODEX_LIVE") != "1":
        pytest.skip("set ORCHESTRATOR_CODEX_LIVE=1 to opt in to Codex live checks")
    home_value = os.environ.get("ORCHESTRATOR_CODEX_HOME")
    model_id = os.environ.get("ORCHESTRATOR_CODEX_LIVE_MODEL")
    if not home_value or not model_id:
        pytest.fail(
            "live checks require a dedicated ORCHESTRATOR_CODEX_HOME and concrete "
            "ORCHESTRATOR_CODEX_LIVE_MODEL"
        )
    home = Path(home_value).expanduser().resolve()
    default_home = (Path.home() / ".codex").resolve()
    if home == default_home or home.is_relative_to(default_home) or home == Path.home().resolve():
        pytest.fail("live checks refuse the default user Codex home")
    effort_value = os.environ.get("ORCHESTRATOR_CODEX_LIVE_EFFORT", "high")
    try:
        effort = Effort(effort_value)
    except ValueError:
        pytest.fail("ORCHESTRATOR_CODEX_LIVE_EFFORT is not a supported project effort")
    return home, model_id, effort


@pytest.fixture
def live_backend(tmp_path, app_config, monkeypatch):
    home, model_id, effort = _live_settings()
    project_path = tmp_path / "read-only-live-fixture"
    project_path.mkdir()
    run_id = f"codex-live-{uuid4()}"
    attempt_id = f"codex-live-attempt-{uuid4()}"
    project = app_config.project.model_copy(
        update={
            "path": str(project_path),
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex", model_id=model_id, allowed_efforts=[effort]
                )
            },
        }
    )
    workflow = next(item for item in app_config.workflows if item.id == "review")
    run_spec = resolve_run(
        "Return one short read-only report.",
        project,
        workflow,
        app_config.agents.agents,
        model_availability={"codex": {model_id: {effort}}},
    )
    spec = _spec(run_id, attempt_id, run_spec.snapshot_hash, model_id, effort)
    stamp = datetime.now(UTC)
    ledger = SQLiteLedger(tmp_path / "codex-live.sqlite3")
    ledger.create_run(run_id, project, run_spec, uuid4(), actor="codex-live-test")
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id=run_id,
            expected_revision=ledger.get_run(run_id).state.revision,
            actor="codex-live-test",
            occurred_at=stamp,
            attempt_creations=(
                AttemptRegistration(
                    spec=spec,
                    stage_id="review",
                    slot_id="review/slot-01",
                    state=AttemptState(attempt_id=attempt_id, status=AttemptStatus.LAUNCHING),
                ),
            ),
        )
    )
    monkeypatch.setenv("ORCHESTRATOR_CODEX_HOME", str(home))
    backend = CodexBackend(
        _settings(),
        ledger=ledger,
        artifact_store=ArtifactStore(tmp_path / "artifacts", ledger),
    )
    context = PreflightContext(
        preparation_id=f"live-preparation-{uuid4()}",
        record_id=f"live-preflight-{uuid4()}",
        project_path=str(project_path),
        required_outputs=("report",),
        binding_id="standard",
    )
    yield backend, context, ledger, spec, stamp, _persist_preflight
    ledger.close()


async def _prepare_live_attempt(backend, context, ledger, spec, stamp, persist):
    preflight = await backend.preflight(spec, context)
    if not preflight.accepted:
        if preflight.prepared_handle is not None:
            receipt = await backend.close(preflight.prepared_handle)
            if not receipt.settled:
                pytest.fail(f"Codex rejected preflight and cleanup is unknown: {receipt.detail}")
        details = "; ".join(issue.message for issue in preflight.issues)
        pytest.skip(f"host policy or Codex auth preflight is blocked: {details}")
    record_id, record_hash = persist(ledger, spec, preflight, context, stamp)
    handle = await backend.start(
        spec,
        preflight_record_id=record_id,
        preflight_record_hash=record_hash,
    )
    identity = WorkerIdentity(
        backend="codex",
        backend_version="0.159.2",
        attempt_id=handle.attempt_id,
        thread_id=handle.thread_id,
        turn_id=handle.turn_id,
        lifecycle_owner_id=handle.lifecycle_owner_id,
    )
    return handle, identity


@pytest.mark.asyncio
async def test_codex_live_one_short_read_only_turn(live_backend) -> None:
    backend, context, ledger, spec, stamp, persist = live_backend
    handle = None
    try:
        async with asyncio.timeout(90):
            handle, _ = await _prepare_live_attempt(backend, context, ledger, spec, stamp, persist)
            events = [event async for event in backend.events(handle)]
        assert any(isinstance(event, WorkerTerminalEvent) for event in events)
    finally:
        if handle is not None:
            receipt = await backend.close(handle)
            assert receipt.settled, receipt.detail


@pytest.mark.asyncio
async def test_codex_live_exact_turn_interrupt_and_cleanup(live_backend) -> None:
    backend, context, ledger, spec, stamp, persist = live_backend
    handle = None
    try:
        async with asyncio.timeout(90):
            handle, identity = await _prepare_live_attempt(
                backend, context, ledger, spec, stamp, persist
            )
            ack = await backend.interrupt(handle, uuid4())
            if not ack.accepted:
                reconciliation = await backend.inspect(identity)
                if reconciliation.known and reconciliation.status is AttemptStatus.SUCCEEDED:
                    pytest.skip("turn completed before the exact-turn interruption; inconclusive")
                pytest.fail(f"exact-turn interruption was rejected: {ack.reason}")
            events = [event async for event in backend.events(handle)]
            if any(isinstance(event, WorkerTerminalEvent) for event in events):
                pytest.skip("turn completed before interruption took effect; inconclusive")
            failure = next(
                (event for event in events if isinstance(event, WorkerFailureEvent)), None
            )
            assert failure is not None and failure.failure_class == "cancelled"
    finally:
        if handle is not None:
            receipt = await backend.close(handle)
            assert receipt.settled, receipt.detail
