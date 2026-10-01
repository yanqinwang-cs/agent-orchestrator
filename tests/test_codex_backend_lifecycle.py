from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from orchestrator.artifacts import ArtifactStore
from orchestrator.backends.codex import CodexBackend
from orchestrator.domain.backend import (
    PreflightContext,
    SteerCommand,
    WorkerDisconnectedEvent,
    WorkerFailureEvent,
    WorkerIdentity,
    WorkerProgressEvent,
    WorkerStartedEvent,
    WorkerTerminalEvent,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    AttemptState,
    AttemptStatus,
    BackendPreflightRecordedEvent,
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

REPORT = (
    b'{"schema_version":1,"status":"pass","summary":"No blocking issues were found.","findings":[]}'
)


class OfflineOwner:
    def __init__(self, **kwargs) -> None:
        self.owner_id = kwargs["owner_id"]
        self.generation = kwargs["generation"]
        self.environment = kwargs["environment"]
        self.child_reaped = False
        self.process_group_empty = False
        self.bridge_disconnected = False
        self.stopped = False
        self.force_unsettled = False

    def bridge_command(self) -> tuple[str, ...]:
        return ("offline-bridge",)

    def status(self) -> dict[str, object]:
        settled = self.child_reaped and self.process_group_empty and self.bridge_disconnected
        return {
            "owner_id": self.owner_id,
            "generation": self.generation,
            "child_reaped": self.child_reaped,
            "process_group_empty": self.process_group_empty,
            "bridge_disconnected": self.bridge_disconnected,
            "settled": settled,
        }

    def terminate_child(self) -> dict[str, object]:
        self.child_reaped = True
        self.process_group_empty = not self.force_unsettled
        return self.status()

    def settled(self, timeout_seconds: float) -> dict[str, object] | None:
        del timeout_seconds
        receipt = self.status()
        return receipt if receipt["settled"] else None

    def stop(self) -> dict[str, object]:
        self.stopped = True
        return self.status()

    def wait(self, timeout_seconds: float) -> bool:
        del timeout_seconds
        return self.stopped


class OfflineCodexSDK:
    def __init__(self, owner: OfflineOwner, project: Path) -> None:
        self.owner = owner
        self.project = project
        self.calls: list[tuple[str, object]] = []
        self.turn_notifications: asyncio.Queue[object] = asyncio.Queue()
        self.turn_count = 0
        self.thread_id = "thread-offline-1"
        self.turn_id = "turn-offline-1"
        self.config = {
            "model": "gpt-5.6-sol",
            "approvalPolicy": "never",
            "sandboxMode": "read-only",
            "webSearch": "disabled",
            "features": {"multi_agent": False},
        }
        self.interrupt_response: object = SimpleNamespace(turn_id=self.turn_id)
        self.history: object | None = None
        self.before_turn_reply: list[object] = []
        self.before_turn_start = None
        self.turn_start_error: Exception | None = None
        self.hold_turn_start = False
        self.turn_start_entered = asyncio.Event()
        self.release_turn_start = asyncio.Event()
        self.closed = False

    async def start(self) -> None:
        self.calls.append(("start", None))

    async def initialize(self) -> object:
        self.calls.append(("initialize", None))
        return SimpleNamespace(
            serverInfo=SimpleNamespace(name="codex-app-server", version="0.159.2")
        )

    async def account_read(self) -> object:
        self.calls.append(("account_read", None))
        return SimpleNamespace(account=SimpleNamespace(root=SimpleNamespace(type="chatgpt")))

    async def model_list(self) -> object:
        self.calls.append(("model_list", None))
        return SimpleNamespace(
            data=(
                SimpleNamespace(
                    id="gpt-5.6-sol",
                    supported_reasoning_efforts=(
                        SimpleNamespace(reasoning_effort=SimpleNamespace(value="high")),
                    ),
                ),
            )
        )

    async def request(self, method: str, params: object, *, response_model: type) -> object:
        del response_model
        self.calls.append((method, params))
        if method != "config/read":
            raise AssertionError(f"unexpected SDK method: {method}")
        config = SimpleNamespace(model_dump=lambda **kwargs: dict(self.config))
        return SimpleNamespace(config=config, layers=(SimpleNamespace(config=dict(self.config)),))

    async def thread_start(self, params: object) -> object:
        self.calls.append(("thread_start", params))
        return SimpleNamespace(
            thread=SimpleNamespace(id=self.thread_id, ephemeral=False),
            model="gpt-5.6-sol",
            model_provider="openai",
            reasoning_effort=SimpleNamespace(value="high"),
            cwd=SimpleNamespace(root=str(self.project)),
            approval_policy=SimpleNamespace(root="never"),
            sandbox=SimpleNamespace(root=SimpleNamespace(type="readOnly", network_access=False)),
            instruction_sources=(),
        )

    async def turn_start(self, thread_id: str, prompt: str, params: object) -> object:
        self.calls.append(("turn_start", (thread_id, prompt, params)))
        self.turn_count += 1
        if self.before_turn_start is not None:
            self.before_turn_start()
        if self.hold_turn_start:
            self.turn_start_entered.set()
            await self.release_turn_start.wait()
        if self.turn_start_error is not None:
            raise self.turn_start_error
        for notification in self.before_turn_reply:
            self.turn_notifications.put_nowait(notification)
        return SimpleNamespace(turn=SimpleNamespace(id=self.turn_id, status="inProgress", items=()))

    async def next_turn_notification(self, turn_id: str) -> object:
        assert turn_id == self.turn_id
        notification = await self.turn_notifications.get()
        if isinstance(notification, BaseException):
            raise notification
        return notification

    async def turn_interrupt(self, thread_id: str, turn_id: str) -> object:
        self.calls.append(("turn_interrupt", (thread_id, turn_id)))
        if isinstance(self.interrupt_response, BaseException):
            raise self.interrupt_response
        return self.interrupt_response

    async def thread_read(self, thread_id: str, *, include_turns: bool) -> object:
        self.calls.append(("thread_read", (thread_id, include_turns)))
        assert self.history is not None
        return self.history

    async def close(self) -> None:
        self.calls.append(("close", None))
        self.closed = True
        self.owner.bridge_disconnected = True
        self.release_turn_start.set()


def _spec(run_id: str, attempt_id: str, run_snapshot_hash: str) -> AgentRunSpec:
    return AgentRunSpec(
        run_id=run_id,
        attempt_id=attempt_id,
        profile_id="reviewer",
        profile_version="1.0.0",
        instructions="Review the patch without changing files.",
        input_manifest=(),
        backend="codex",
        model_id="gpt-5.6-sol",
        effort="high",
        permissions=PermissionSet(
            sandbox=SandboxMode.READ_ONLY,
            shell_network=False,
            web_search=False,
            external_integrations=False,
            nested_agents=False,
        ),
        skills=(),
        tools=("read_files",),
        run_snapshot_hash=run_snapshot_hash,
    )


def _settings():
    from orchestrator.domain.models import ApprovalMode, CodexBackendSettings

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
        interrupt_grace_seconds=2,
        shutdown_grace_seconds=1,
        allow_unverified_policy=False,
    )


def _record_accepted_preflight(ledger, spec, result, context, occurred_at):
    assert result.snapshot is not None and result.prepared_handle is not None
    record = BackendPreflightRecord(
        record_id=context.record_id,
        run_id=spec.run_id,
        attempt_id=spec.attempt_id,
        preparation_id=context.preparation_id,
        attempt_spec_hash=content_hash(canonical_json(spec)),
        accepted=True,
        occurred_at=occurred_at,
        snapshot=result.snapshot,
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
    event = BackendPreflightRecordedEvent(
        event_id=uuid4(),
        run_id=spec.run_id,
        occurred_at=occurred_at,
        actor="offline-test",
        kind=EventKind.BACKEND_PREFLIGHT_RECORDED,
        record_id=record.record_id,
        attempt_id=record.attempt_id,
        preparation_id=record.preparation_id,
        record_hash=record.record_hash,
        accepted=True,
    )
    state = attempt.state.model_copy(
        update={
            "backend_preflight_record_id": record.record_id,
            "backend_preflight_record_hash": record.record_hash,
            "worker_handle_id": result.prepared_handle.handle_id,
            "worker_backend_version": result.prepared_handle.backend_version,
            "worker_session_id": None,
            "worker_thread_id": result.prepared_handle.thread_id,
            "worker_turn_id": None,
            "worker_lifecycle_owner_id": result.prepared_handle.lifecycle_owner_id,
        }
    )
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id=spec.run_id,
            expected_revision=run.state.revision,
            actor="offline-test",
            occurred_at=occurred_at,
            attempt_updates=(state,),
            backend_preflight_records=(record,),
            events=(event,),
        )
    )
    return record.record_id, record.record_hash


@pytest.fixture
def lifecycle(tmp_path, app_config, monkeypatch):
    stamp = datetime(2026, 10, 1, tzinfo=UTC)
    project_config = app_config.project.model_copy(
        update={
            "models": {
                "standard": ModelBindingSettings(
                    backend="codex", model_id="gpt-5.6-sol", allowed_efforts=[Effort.HIGH]
                )
            }
        }
    )
    workflow = next(item for item in app_config.workflows if item.id == "review")
    run_spec = resolve_run(
        "Review the patch",
        project_config,
        workflow,
        app_config.agents.agents,
        model_availability={"codex": {"gpt-5.6-sol": {Effort.HIGH}}},
    )
    ledger = SQLiteLedger(tmp_path / "codex-lifecycle.sqlite3")
    ledger.create_run("run-codex", project_config, run_spec, uuid4(), actor="offline-test")
    spec = _spec("run-codex", "attempt-codex", run_spec.snapshot_hash)
    ledger.apply(
        LedgerMutation(
            command_id=uuid4(),
            run_id="run-codex",
            expected_revision=ledger.get_run("run-codex").state.revision,
            actor="offline-test",
            occurred_at=stamp,
            attempt_creations=(
                AttemptRegistration(
                    spec=spec,
                    stage_id="review",
                    slot_id="review/slot-01",
                    state=AttemptState(attempt_id=spec.attempt_id, status=AttemptStatus.LAUNCHING),
                ),
            ),
        )
    )
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "dedicated-codex-home"
    monkeypatch.setenv("ORCHESTRATOR_CODEX_HOME", str(home))
    owners: list[OfflineOwner] = []
    clients: list[OfflineCodexSDK] = []

    def owner_factory(**kwargs):
        owner = OfflineOwner(**kwargs)
        owners.append(owner)
        return owner

    def client_factory():
        client = OfflineCodexSDK(owners[-1], project)
        clients.append(client)
        return client

    backend = CodexBackend(
        _settings(),
        client_factory=client_factory,
        owner_factory=owner_factory,
        ledger=ledger,
        artifact_store=ArtifactStore(tmp_path / "artifacts", ledger),
    )
    context = PreflightContext(
        preparation_id="offline-preparation-1",
        record_id="offline-preflight-1",
        project_path=str(project),
        required_outputs=("report",),
        binding_id="codex-reviewer",
    )
    yield SimpleNamespace(
        backend=backend,
        context=context,
        ledger=ledger,
        spec=spec,
        stamp=stamp,
        project=project,
        home=home,
        owners=owners,
        clients=clients,
    )
    ledger.close()


async def _prepare_and_start(lifecycle):
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    assert result.accepted
    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    handle = await lifecycle.backend.start(
        lifecycle.spec,
        preflight_record_id=record_id,
        preflight_record_hash=record_hash,
    )
    return result, handle


@pytest.mark.asyncio
async def test_codex_turn_keeps_early_notifications_and_waits_for_owner_settlement(
    lifecycle, repo_root
) -> None:
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    assert result.accepted
    owner = lifecycle.owners[-1]
    client = lifecycle.clients[-1]
    assert set(owner.environment) == {"HOME", "CODEX_HOME", "PATH", "TMPDIR", "LANG"}
    assert owner.environment["CODEX_HOME"] == str(lifecycle.home)

    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    client.before_turn_start = lambda: lifecycle.ledger.get_backend_preflight_record(record_id)
    client.before_turn_reply = [
        SimpleNamespace(
            method="item/started",
            payload=SimpleNamespace(
                thread_id=client.thread_id,
                turn_id=client.turn_id,
                item=SimpleNamespace(type="agentMessage"),
            ),
        ),
        SimpleNamespace(
            method="thread/tokenUsage/updated",
            payload=SimpleNamespace(
                thread_id=client.thread_id,
                turn_id=client.turn_id,
                token_usage=SimpleNamespace(
                    last=SimpleNamespace(input_tokens=31, output_tokens=None, total_tokens=-1)
                ),
            ),
        ),
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=client.thread_id,
                turn=SimpleNamespace(
                    id=client.turn_id,
                    status="completed",
                    items=(SimpleNamespace(type="agentMessage", text=REPORT.decode()),),
                ),
            ),
        ),
    ]
    handle = await lifecycle.backend.start(
        lifecycle.spec,
        preflight_record_id=record_id,
        preflight_record_hash=record_hash,
    )
    events = [event async for event in lifecycle.backend.events(handle)]
    assert isinstance(events[0], WorkerStartedEvent)
    assert any(isinstance(event, WorkerProgressEvent) for event in events)
    terminal = next(event for event in events if isinstance(event, WorkerTerminalEvent))
    assert terminal.result.summary == "No blocking issues were found."
    assert terminal.result.usage is not None
    assert terminal.result.usage.input_tokens == 31
    assert terminal.result.usage.output_tokens is None
    assert terminal.result.usage.total_tokens is None
    assert owner.status()["settled"] is True
    assert client.closed
    assert client.turn_count == 1
    identity = WorkerIdentity(
        backend="codex",
        backend_version="0.159.2",
        attempt_id=handle.attempt_id,
        thread_id=handle.thread_id,
        turn_id=handle.turn_id,
        lifecycle_owner_id=handle.lifecycle_owner_id,
    )
    reconciliation = await lifecycle.backend.inspect(identity)
    assert reconciliation.known
    assert reconciliation.terminal_result == terminal.result
    assert (await lifecycle.backend.close(handle)).settled
    fixture = json.loads((repo_root / "tests/fixtures/backends/codex-sdk-0.159.2.json").read_text())
    assert fixture["fixture_kind"] == "synthetic_offline"


@pytest.mark.asyncio
async def test_exact_interrupt_is_idempotent_and_unacknowledged_interrupt_is_unknown(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    command_id = uuid4()
    steer_ack = await lifecycle.backend.steer(
        handle,
        SteerCommand(
            command_id=uuid4(), attempt_id=handle.attempt_id, instruction="change direction"
        ),
    )
    assert not steer_ack.supported
    assert not any(call[0] == "turn/steer" for call in client.calls)
    assert (await lifecycle.backend.interrupt(handle, command_id)).accepted
    assert (await lifecycle.backend.interrupt(handle, command_id)).accepted
    assert [call for call in client.calls if call[0] == "turn_interrupt"] == [
        ("turn_interrupt", (handle.thread_id, handle.turn_id))
    ]
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(id=handle.turn_id, status="interrupted", items=()),
            ),
        )
    )
    events = [event async for event in lifecycle.backend.events(handle)]
    failure = next(event for event in events if isinstance(event, WorkerFailureEvent))
    assert failure.failure_class.value == "cancelled"


@pytest.mark.asyncio
async def test_interrupt_rejects_foreign_owner_thread_and_turn(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    foreign_handle = handle.model_copy(
        update={
            "thread_id": "sibling-thread",
            "turn_id": "sibling-turn",
            "lifecycle_owner_id": "sibling-owner",
        }
    )

    acknowledgement = await lifecycle.backend.interrupt(foreign_handle, uuid4())

    assert not acknowledgement.accepted
    assert not [call for call in lifecycle.clients[-1].calls if call[0] == "turn_interrupt"]


@pytest.mark.asyncio
async def test_rejected_exact_interrupt_is_cached_without_replay(lifecycle):
    from openai_codex.errors import InvalidRequestError

    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    client.interrupt_response = InvalidRequestError(-32600, "turn is no longer active")
    command_id = uuid4()
    first = await lifecycle.backend.interrupt(handle, command_id)
    second = await lifecycle.backend.interrupt(handle, command_id)
    assert not first.accepted and not second.accepted
    assert len([call for call in client.calls if call[0] == "turn_interrupt"]) == 1


@pytest.mark.asyncio
async def test_provider_terminal_is_not_success_until_process_owner_settles(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    owner = lifecycle.owners[-1]
    owner.force_unsettled = True
    lifecycle.clients[-1].turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(
                    id=handle.turn_id,
                    status="completed",
                    items=(SimpleNamespace(type="agentMessage", text=REPORT.decode()),),
                ),
            ),
        )
    )
    events = [event async for event in lifecycle.backend.events(handle)]
    assert any(isinstance(event, WorkerDisconnectedEvent) for event in events)
    assert not any(isinstance(event, WorkerTerminalEvent) for event in events)
    assert not (await lifecycle.backend.close(handle)).settled


@pytest.mark.asyncio
async def test_failed_provider_terminal_maps_to_failure_after_owner_settlement(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    lifecycle.clients[-1].turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(id=handle.turn_id, status="failed", items=()),
            ),
        )
    )

    events = [event async for event in lifecycle.backend.events(handle)]

    failure = next(event for event in events if isinstance(event, WorkerFailureEvent))
    assert failure.failure_class.value == "worker_failure"
    assert lifecycle.owners[-1].status()["settled"]


@pytest.mark.asyncio
async def test_configuration_drift_rejects_before_turn_submission_and_settles_owner(lifecycle):
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    assert result.accepted
    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    client = lifecycle.clients[-1]
    client.config["webSearch"] = "enabled"
    with pytest.raises(Exception, match="effective configuration changed"):
        await lifecycle.backend.start(
            lifecycle.spec,
            preflight_record_id=record_id,
            preflight_record_hash=record_hash,
        )
    assert client.turn_count == 0
    assert client.closed
    assert lifecycle.owners[-1].status()["settled"]


@pytest.mark.asyncio
async def test_fresh_reader_does_not_treat_synthetic_interrupted_history_as_settlement(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    fresh_reader = CodexBackend(_settings(), ledger=lifecycle.ledger)
    reconciliation = await fresh_reader.inspect(
        WorkerIdentity(
            backend="codex",
            backend_version="0.159.2",
            attempt_id=handle.attempt_id,
            thread_id=handle.thread_id,
            turn_id=handle.turn_id,
            lifecycle_owner_id=handle.lifecycle_owner_id,
        )
    )
    assert not reconciliation.known
    assert reconciliation.detail is not None


@pytest.mark.asyncio
async def test_notification_eof_without_correlated_terminal_remains_unknown(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    lifecycle.clients[-1].turn_notifications.put_nowait(ConnectionError("offline EOF"))
    events = [event async for event in lifecycle.backend.events(handle)]
    assert any(isinstance(event, WorkerDisconnectedEvent) for event in events)
    identity = WorkerIdentity(
        backend="codex",
        backend_version="0.159.2",
        attempt_id=handle.attempt_id,
        thread_id=handle.thread_id,
        turn_id=handle.turn_id,
        lifecycle_owner_id=handle.lifecycle_owner_id,
    )
    assert not (await lifecycle.backend.inspect(identity)).known


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("bad_config", "issue_code"),
    [
        ({"webSearch": "enabled"}, "web_search_enabled"),
        ({"mcpServers": {"unreviewed": {}}}, "integration_or_delegation_configured"),
        ({"features": {"multi_agent": True}}, "nested_agent_policy_unverified"),
        ({"unknownCapability": True}, "config_layer_has_unreviewed_keys"),
    ],
)
async def test_preflight_rejects_unverified_configuration_before_thread_creation(
    lifecycle, bad_config, issue_code
):
    client_config = {
        "model": "gpt-5.6-sol",
        "approvalPolicy": "never",
        "sandboxMode": "read-only",
        "webSearch": "disabled",
        "features": {"multi_agent": False},
    }
    client_config.update(bad_config)
    original_factory = lifecycle.backend._client_factory

    def client_factory():
        client = original_factory()
        client.config = dict(client_config)
        return client

    lifecycle.backend._client_factory = client_factory
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    assert not result.accepted
    assert issue_code in {issue.code for issue in result.issues}
    assert not any(call[0] == "thread_start" for call in lifecycle.clients[-1].calls)
    assert result.prepared_handle is not None
    assert (await lifecycle.backend.close(result.prepared_handle)).settled


@pytest.mark.asyncio
async def test_lost_turn_start_ack_is_single_use_and_never_replayed(lifecycle):
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    client = lifecycle.clients[-1]
    client.turn_start_error = ConnectionError("start acknowledgement lost")
    with pytest.raises(ConnectionError):
        await lifecycle.backend.start(
            lifecycle.spec,
            preflight_record_id=record_id,
            preflight_record_hash=record_hash,
        )
    assert client.turn_count == 1
    assert client.closed
    with pytest.raises(RuntimeError, match="single-use"):
        await lifecycle.backend.start(
            lifecycle.spec,
            preflight_record_id=record_id,
            preflight_record_hash=record_hash,
        )
    assert client.turn_count == 1


@pytest.mark.asyncio
async def test_cancelled_start_closes_owner_and_late_sdk_reply_is_not_replayed(lifecycle):
    result = await lifecycle.backend.preflight(lifecycle.spec, lifecycle.context)
    record_id, record_hash = _record_accepted_preflight(
        lifecycle.ledger, lifecycle.spec, result, lifecycle.context, lifecycle.stamp
    )
    client = lifecycle.clients[-1]
    client.hold_turn_start = True
    start_task = asyncio.create_task(
        lifecycle.backend.start(
            lifecycle.spec,
            preflight_record_id=record_id,
            preflight_record_hash=record_hash,
        )
    )
    await asyncio.wait_for(client.turn_start_entered.wait(), timeout=2)
    start_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await start_task
    await asyncio.wait_for(client.release_turn_start.wait(), timeout=2)
    await asyncio.sleep(0)
    assert client.turn_count == 1
    assert client.closed
    assert lifecycle.owners[-1].status()["settled"]


@pytest.mark.asyncio
async def test_original_owner_can_reconcile_terminal_history_only_after_settlement(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    client.history = SimpleNamespace(
        thread=SimpleNamespace(
            id=handle.thread_id,
            turns=(
                SimpleNamespace(
                    id=handle.turn_id,
                    status="completed",
                    items=(SimpleNamespace(type="agentMessage", text=REPORT.decode()),),
                ),
            ),
        )
    )
    reconciliation = await lifecycle.backend.inspect(
        WorkerIdentity(
            backend="codex",
            backend_version="0.159.2",
            attempt_id=handle.attempt_id,
            thread_id=handle.thread_id,
            turn_id=handle.turn_id,
            lifecycle_owner_id=handle.lifecycle_owner_id,
        )
    )
    assert reconciliation.known
    assert reconciliation.terminal_result is not None
    assert lifecycle.owners[-1].status()["settled"]


@pytest.mark.asyncio
async def test_uncertain_interrupt_is_never_replayed_and_does_not_claim_cancellation(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    client.interrupt_response = ConnectionError("offline acknowledgement loss")
    command_id = uuid4()
    with pytest.raises(ConnectionError):
        await lifecycle.backend.interrupt(handle, command_id)
    with pytest.raises(RuntimeError, match="uncertain delivery outcome"):
        await lifecycle.backend.interrupt(handle, command_id)
    assert len([call for call in client.calls if call[0] == "turn_interrupt"]) == 1
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(id=handle.turn_id, status="interrupted", items=()),
            ),
        )
    )
    events = [event async for event in lifecycle.backend.events(handle)]
    assert any(isinstance(event, WorkerDisconnectedEvent) for event in events)
    assert not any(isinstance(event, WorkerFailureEvent) for event in events)


@pytest.mark.asyncio
async def test_preparation_owner_without_committed_thread_turn_stays_unknown(tmp_path, monkeypatch):
    from orchestrator.backends import codex_backend as codex_backend_module

    owner_id = "persisted-preparation-owner"
    monkeypatch.setenv("ORCHESTRATOR_CODEX_HOME", str(tmp_path / "dedicated-home"))
    monkeypatch.setattr(
        codex_backend_module,
        "query_owner_status",
        lambda found_owner, generation: (
            {"owner_id": found_owner, "generation": generation, "settled": False}
            if found_owner == owner_id
            else None
        ),
    )
    backend = CodexBackend(_settings())

    reconciliation = await backend.inspect(
        WorkerIdentity(
            backend="codex",
            attempt_id="attempt-before-thread",
            lifecycle_owner_id=owner_id,
        )
    )

    assert reconciliation.known is False
    assert "active without committed thread and turn" in (reconciliation.detail or "")


@pytest.mark.asyncio
async def test_unknown_notification_uses_raw_sdk_identity_without_retaining_payload(lifecycle):
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="future/notification",
            payload=SimpleNamespace(
                params={
                    "threadId": handle.thread_id,
                    "turnId": handle.turn_id,
                    "diagnostic": "sensitive provider text",
                }
            ),
        )
    )
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(
                    id=handle.turn_id,
                    status="completed",
                    items=(SimpleNamespace(type="agentMessage", text=REPORT.decode()),),
                ),
            ),
        )
    )

    events = [event async for event in lifecycle.backend.events(handle)]

    progress = next(event for event in events if isinstance(event, WorkerProgressEvent))
    assert progress.message == "future/notification"
    assert "sensitive provider text" not in progress.message
    assert any(isinstance(event, WorkerTerminalEvent) for event in events)


@pytest.mark.asyncio
@pytest.mark.parametrize("mismatched_id", ["thread", "turn"])
async def test_unknown_notification_with_wrong_raw_sdk_identity_disconnects(
    lifecycle, mismatched_id
):
    _, handle = await _prepare_and_start(lifecycle)
    client = lifecycle.clients[-1]
    thread_id = "thread-from-another-attempt" if mismatched_id == "thread" else handle.thread_id
    turn_id = handle.turn_id if mismatched_id == "thread" else "turn-from-another-attempt"
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="future/notification",
            payload=SimpleNamespace(params={"threadId": thread_id, "turnId": turn_id}),
        )
    )
    client.turn_notifications.put_nowait(
        SimpleNamespace(
            method="turn/completed",
            payload=SimpleNamespace(
                thread_id=handle.thread_id,
                turn=SimpleNamespace(
                    id=handle.turn_id,
                    status="completed",
                    items=(SimpleNamespace(type="agentMessage", text=REPORT.decode()),),
                ),
            ),
        )
    )

    events = [event async for event in lifecycle.backend.events(handle)]

    assert any(isinstance(event, WorkerDisconnectedEvent) for event in events)
    assert not any(isinstance(event, WorkerTerminalEvent) for event in events)
