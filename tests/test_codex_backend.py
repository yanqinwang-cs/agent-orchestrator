from __future__ import annotations

import json
import platform
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from orchestrator.backends.codex import CodexBackend
from orchestrator.backends.fake import AttemptScript, FakeBackend, FakeClock
from orchestrator.domain.backend import (
    BackendPreflightSnapshot,
    PreflightContext,
    PreflightResult,
    SteerCommand,
    WorkerFailureEvent,
    WorkerHandle,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    ApprovalMode,
    CodexBackendSettings,
    Effort,
    FailureClass,
    ModelBindingSettings,
    PermissionSet,
    RunStatus,
    SandboxMode,
)
from orchestrator.execution import ExecutionCoordinator
from orchestrator.persistence import CoordinatorOwnership, SQLiteLedger
from orchestrator.resolution import resolve_run


def _spec() -> AgentRunSpec:
    return AgentRunSpec(
        run_id="run-1",
        attempt_id="attempt-1",
        profile_id="reviewer",
        profile_version="1.0.0",
        instructions="Review the patch",
        input_manifest=(),
        backend="codex",
        model_id="gpt-5.6-sol",
        effort="high",
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
        run_snapshot_hash="a" * 64,
    )


def _settings() -> CodexBackendSettings:
    return CodexBackendSettings(
        kind="codex_sdk",
        sdk_package="openai-codex",
        sdk_version="0.159.2",
        cli_source="sdk_pinned_dependency",
        client_per_attempt=True,
        auth_owner="codex",
        codex_home_env="ORCHESTRATOR_CODEX_HOME",
        approval_mode="deny_all",
        experimental_api=False,
        interrupt_grace_seconds=10,
        shutdown_grace_seconds=5,
        allow_unverified_policy=False,
    )


async def test_codex_preflight_fails_closed_without_host_compatibility_evidence(
    repo_root,
) -> None:
    fixture = json.loads((repo_root / "tests/fixtures/backends/codex-sdk-0.159.2.json").read_text())
    client_factory_calls = 0

    def client_factory():
        nonlocal client_factory_calls
        client_factory_calls += 1
        raise AssertionError("preflight must reject before creating an SDK client")

    backend = CodexBackend(_settings(), client_factory=client_factory)
    result = await backend.preflight(
        _spec(),
        PreflightContext(
            preparation_id="prep-1",
            record_id="record-1",
            project_path="/tmp/project",
            required_outputs=("review_report",),
            binding_id="codex-reviewer",
        ),
    )

    assert result.accepted is False
    assert {issue.code for issue in result.issues} >= {
        "sanitized_launch_unverified",
        "process_settlement_unverified",
        "effective_policy_unverified",
    }
    assert result.snapshot is not None
    runtime_facts = {fact.key: fact for fact in result.snapshot.runtime}
    assert runtime_facts["sdk_version"].value == fixture["sdk"]["version"]
    assert runtime_facts["cli_version"].value == fixture["cli"]["version"]
    assert runtime_facts["audited_source_revision"].value == fixture["sdk"]["source_revision"]
    if platform.system() == "Darwin" and platform.machine() == "arm64":
        assert runtime_facts["cli_sha256"].value == fixture["cli"]["sha256"]
    capabilities = await backend.capabilities()
    assert capabilities.steering is False
    assert capabilities.output_schemas == ()
    command = SteerCommand(
        command_id=uuid4(),
        attempt_id="attempt-1",
        instruction="change direction",
    )
    handle = WorkerHandle(
        handle_id="codex-attempt-1",
        backend="codex",
        backend_version="0.159.2",
        attempt_id="attempt-1",
        thread_id="thread-1",
        turn_id="turn-1",
        lifecycle_owner_id="owner-1",
    )
    steer_ack = await backend.steer(handle, command)
    interrupt_ack = await backend.interrupt(handle, command.command_id)
    assert steer_ack.supported is False
    assert steer_ack.accepted is False
    assert interrupt_ack.accepted is False
    assert client_factory_calls == 0


def test_alternate_service_owned_capabilities_fixture_is_explicit_and_bounded(repo_root) -> None:
    fixture = json.loads(
        (repo_root / "tests/fixtures/backends/codex-alternate-ownership.json").read_text()
    )

    assert fixture["fixture_kind"] == "synthetic_offline"
    assert fixture["provider_traffic"] is False
    capabilities = {item["name"]: item for item in fixture["capabilities"]}
    for capability in ("filesystem_read", "terminal"):
        assert capabilities[capability]["execution_owner"] == "service"
        assert capabilities[capability]["enforcement_owner"] == "service"
        assert capabilities[capability]["settlement_owner"] == "service"
        assert capabilities[capability]["state"] == "verified"
    builtin_tools = capabilities["codex_builtin_tools"]
    assert builtin_tools["state"] == "unsupported"
    assert builtin_tools["execution_owner"] is None


@pytest.mark.asyncio
async def test_codex_preflight_rejects_write_requests_before_sdk_client_creation() -> None:
    client_factory_calls = 0

    def client_factory():
        nonlocal client_factory_calls
        client_factory_calls += 1
        raise AssertionError("write attempts must be rejected before SDK client creation")

    backend = CodexBackend(_settings(), client_factory=client_factory)
    write_spec = _spec().model_copy(
        update={"permissions": PermissionSet(sandbox=SandboxMode.WORKSPACE_WRITE)}
    )
    result = await backend.preflight(
        write_spec,
        PreflightContext(
            preparation_id="prep-write",
            record_id="record-write",
            project_path="/tmp/project",
            required_outputs=("report",),
            binding_id="codex-reviewer",
        ),
    )

    assert result.accepted is False
    assert "write_permission_unsupported" in {issue.code for issue in result.issues}
    assert client_factory_calls == 0


@pytest.mark.asyncio
async def test_coordinator_commits_rejected_codex_preflight_before_settling(
    tmp_path, app_config
) -> None:
    stamp = datetime(2026, 9, 30, tzinfo=UTC)
    project = app_config.project.model_copy(
        update={
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex", model_id="offline-model", allowed_efforts=[Effort.HIGH]
                )
            }
        }
    )
    workflow = next(item for item in app_config.workflows if item.id == "review")
    spec = resolve_run(
        "Review the current changes",
        project,
        workflow,
        app_config.agents.agents,
        model_availability={"codex": {"offline-model": {Effort.HIGH}}},
    )
    ledger = SQLiteLedger(tmp_path / "codex-preflight.sqlite3")
    ledger.create_run("run-codex", project, spec, uuid4(), actor="test", occurred_at=stamp)
    ownership = CoordinatorOwnership(ledger, tmp_path / "coordinator.lock")
    ownership.acquire("codex-test-owner", stamp)
    backend = CodexBackend(_settings())
    coordinator = ExecutionCoordinator(
        ledger,
        backend,
        ownership,
        clock=FakeClock(origin=stamp),
    )

    status = await coordinator.run_until_stalled("run-codex")

    records = ledger.list_backend_preflight_records("run-codex")
    attempts = ledger.list_attempts("run-codex")
    assert status == RunStatus.FAILED
    assert len(records) == 1
    assert records[0].accepted is False
    assert records[0].attempt_id == attempts[0].spec.attempt_id
    assert attempts[0].state.backend_preflight_record_id == records[0].record_id
    assert attempts[0].state.status.value == "failed"
    ownership.release(stamp)
    ledger.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatched_preparation", [False, True])
async def test_coordinator_persists_accepted_snapshot_before_start_and_rejects_mismatch(
    tmp_path, app_config, mismatched_preparation
) -> None:
    stamp = datetime(2026, 9, 30, tzinfo=UTC)
    project = app_config.project.model_copy(
        update={
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex", model_id="offline-model", allowed_efforts=[Effort.HIGH]
                )
            }
        }
    )
    workflow = next(item for item in app_config.workflows if item.id == "review")
    spec = resolve_run(
        "Review the current changes",
        project,
        workflow,
        app_config.agents.agents,
        model_availability={"codex": {"offline-model": {Effort.HIGH}}},
    )
    ledger = SQLiteLedger(tmp_path / "snapshot-order.sqlite3")
    ledger.create_run("run-order", project, spec, uuid4(), actor="test", occurred_at=stamp)
    ownership = CoordinatorOwnership(ledger, tmp_path / "coordinator.lock")
    ownership.acquire("snapshot-test-owner", stamp)

    class OrderingBackend(FakeBackend):
        def __init__(self) -> None:
            super().__init__(
                backend_id="codex",
                script_factory=lambda attempt: AttemptScript(
                    events=(
                        WorkerFailureEvent(
                            kind="failed",
                            attempt_id=attempt.attempt_id,
                            sequence=1,
                            failure_class=FailureClass.WORKER_FAILURE,
                            summary="offline lifecycle fixture",
                        ),
                    )
                ),
                auto_release=True,
            )
            self.start_saw_record = False

        async def preflight(self, spec, context=None):
            assert context is not None
            return PreflightResult(
                accepted=True,
                snapshot=BackendPreflightSnapshot(
                    preparation_id=(
                        "wrong-preparation" if mismatched_preparation else context.preparation_id
                    ),
                    observed_at=stamp,
                ),
            )

        async def start(
            self,
            spec,
            *,
            preflight_record_id=None,
            preflight_record_hash=None,
        ):
            assert preflight_record_id is not None
            persisted = ledger.get_backend_preflight_record(preflight_record_id)
            assert persisted.accepted
            assert persisted.record_hash == preflight_record_hash
            self.start_saw_record = True
            return await super().start(
                spec,
                preflight_record_id=preflight_record_id,
                preflight_record_hash=preflight_record_hash,
            )

    backend = OrderingBackend()
    coordinator = ExecutionCoordinator(
        ledger,
        backend,
        ownership,
        clock=FakeClock(origin=stamp),
    )
    status = await coordinator.run_until_stalled("run-order")

    assert status == RunStatus.FAILED
    assert backend.start_saw_record is not mismatched_preparation
    assert bool(backend.start_calls) is not mismatched_preparation
    assert bool(ledger.list_backend_preflight_records("run-order")) is not mismatched_preparation
    ownership.release(stamp)
    ledger.close()
