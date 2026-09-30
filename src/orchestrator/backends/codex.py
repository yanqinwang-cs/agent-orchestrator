"""Pinned Codex backend boundary with fail-closed host activation checks.

The SDK and CLI are inspected locally during preflight. This checkout does not yet
have independently verified launch sanitization, child settlement, or effective
policy enforcement, so no SDK client is created and no provider request is sent.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import importlib.resources
import json
import os
import subprocess
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from orchestrator.backends.protocol import KnownPrelaunchFailure
from orchestrator.domain.backend import (
    BackendCapabilities,
    BackendPreflightSnapshot,
    ControlAck,
    PreflightContext,
    PreflightFact,
    PreflightIssue,
    PreflightResult,
    Reconciliation,
    ShutdownReceipt,
    SteerCommand,
    WorkerDisconnectedEvent,
    WorkerEvent,
    WorkerEventKind,
    WorkerHandle,
    WorkerIdentity,
)
from orchestrator.domain.models import (
    AgentRunSpec,
    CodexBackendSettings,
    FailureClass,
)

EXPECTED_SDK_VERSION = "0.159.2"
EXPECTED_CLI_VERSION = "0.159.2"
EXPECTED_OUTPUT_SCHEMA = "codex-read-only-result-v1"


class CodexBackend:
    """Codex adapter boundary; runtime activation requires audited host evidence."""

    requires_preflight_record = True

    def __init__(
        self,
        settings: CodexBackendSettings,
        *,
        client_factory: Callable[[], object] | None = None,
    ) -> None:
        self.settings = settings
        self._client_factory = client_factory
        self._prepared: dict[str, str] = {}
        self._handles: dict[str, WorkerHandle] = {}
        self._sequence: dict[str, int] = {}

    async def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            streaming=False,
            steering=False,
            interruption=False,
            saved_history_inspection=False,
            output_schemas=(),
            supported_efforts=(),
            enforceable_permission_settings=(),
            unavailable_controls=(
                ("filesystem_boundary", "host launch and effective policy are not verified"),
                ("process_settlement", "independent owner settlement is not verified"),
                ("sdk_lifecycle", "typed SDK lifecycle mapping is not implemented"),
                ("read_only_output", "output retention helper is not connected to a turn stream"),
                ("steering", "steering is intentionally unsupported"),
            ),
        )

    async def preflight(
        self, spec: AgentRunSpec, context: PreflightContext | None = None
    ) -> PreflightResult:
        context = context or PreflightContext(
            preparation_id=f"unbound:{spec.attempt_id}",
            record_id=f"unbound:{spec.attempt_id}",
            project_path=".",
            required_outputs=(),
        )
        issues: list[PreflightIssue] = []
        sdk_version = self._distribution_version("openai-codex")
        cli_package_version = self._distribution_version("openai-codex-cli-bin")
        cli_path, cli_version, cli_hash = self._inspect_cli()
        if self.settings.sdk_version != EXPECTED_SDK_VERSION or sdk_version != EXPECTED_SDK_VERSION:
            issues.append(
                PreflightIssue(
                    code="sdk_version_mismatch",
                    message="installed Codex SDK does not match the audited exact version",
                    setting="sdk_version",
                )
            )
        if cli_version != EXPECTED_CLI_VERSION or cli_hash is None:
            issues.append(
                PreflightIssue(
                    code="cli_version_unverified",
                    message="the SDK-bundled Codex CLI version or executable hash is unverified",
                    setting="cli_source",
                )
            )
        if cli_package_version != EXPECTED_CLI_VERSION:
            issues.append(
                PreflightIssue(
                    code="cli_package_version_mismatch",
                    message=(
                        "installed SDK-bundled CLI package does not match the audited exact version"
                    ),
                    setting="cli_source",
                )
            )
        if self.settings.experimental_api:
            issues.append(
                PreflightIssue(
                    code="experimental_api_enabled",
                    message="experimental Codex APIs must be disabled for this adapter",
                    setting="experimental_api",
                )
            )
        if not self.settings.client_per_attempt:
            issues.append(
                PreflightIssue(
                    code="client_scope_unsupported",
                    message="each attempt requires a fresh dedicated SDK client",
                    setting="client_per_attempt",
                )
            )
        if self.settings.approval_mode.value != "deny_all":
            issues.append(
                PreflightIssue(
                    code="approval_policy_unsupported",
                    message="Codex M6 requires deny-all approval policy",
                    setting="approval_mode",
                )
            )
        if self.settings.allow_unverified_policy:
            issues.append(
                PreflightIssue(
                    code="unverified_policy_enabled",
                    message="unverified enforcement cannot be allowed for Codex M6",
                    setting="allow_unverified_policy",
                )
            )
        if spec.permissions.sandbox.value != "read-only":
            issues.append(
                PreflightIssue(
                    code="write_permission_unsupported",
                    message="Codex M6 accepts read-only attempts only",
                    setting="permissions.sandbox",
                )
            )
        if (
            spec.permissions.shell_network
            or spec.permissions.web_search
            or spec.permissions.external_integrations
            or spec.permissions.nested_agents
        ):
            issues.append(
                PreflightIssue(
                    code="requested_capability_unsupported",
                    message=(
                        "requested network, web, integration, or nested-agent capability "
                        "is unsupported"
                    ),
                    setting="permissions",
                )
            )
        if context.required_outputs != ("report",):
            issues.append(
                PreflightIssue(
                    code="output_contract_unsupported",
                    message="Codex M6 supports only the single read-only report output contract",
                    setting="required_outputs",
                )
            )
        if not os.environ.get(self.settings.codex_home_env):
            issues.append(
                PreflightIssue(
                    code="dedicated_codex_home_missing",
                    message="set the configured dedicated Codex home before preparing an attempt",
                    setting=self.settings.codex_home_env,
                )
            )
        elif not self._is_dedicated_home(os.environ[self.settings.codex_home_env]):
            issues.append(
                PreflightIssue(
                    code="codex_home_not_dedicated",
                    message=(
                        "the configured Codex home must be separate from the user's default home"
                    ),
                    setting=self.settings.codex_home_env,
                )
            )

        # These three host facts are required for activation. They are not
        # inferred from SDK settings, a dedicated home, or a process ID.
        issues.extend(
            (
                PreflightIssue(
                    code="sanitized_launch_unverified",
                    message=(
                        "the pinned SDK launch path has no demonstrated sanitized child environment"
                    ),
                    setting="runtime.environment",
                ),
                PreflightIssue(
                    code="process_settlement_unverified",
                    message="independent process-owner settlement is not demonstrated on this host",
                    setting="runtime.process_owner",
                ),
                PreflightIssue(
                    code="effective_policy_unverified",
                    message=(
                        "the pinned runtime's effective configuration and integration "
                        "restrictions are not verified"
                    ),
                    setting="runtime.effective_policy",
                ),
                PreflightIssue(
                    code="provider_preparation_unavailable",
                    message=(
                        "account, model, effective configuration, and thread checks are not "
                        "implemented"
                    ),
                    setting="runtime.preparation",
                ),
            )
        )

        observed = datetime.now(UTC)
        home = os.environ.get(self.settings.codex_home_env)
        dedicated_home = bool(home and self._is_dedicated_home(home))
        home_identity = self._home_identity(home) if dedicated_home and home else None
        config_fingerprint = hashlib.sha256(
            json.dumps(self.settings.model_dump(mode="json"), sort_keys=True).encode()
        ).hexdigest()
        project_fingerprint = hashlib.sha256(
            str(Path(context.project_path).expanduser().resolve()).encode()
        ).hexdigest()
        snapshot = BackendPreflightSnapshot(
            preparation_id=context.preparation_id,
            observed_at=observed,
            runtime=(
                PreflightFact(
                    key="sdk_version",
                    value=sdk_version,
                    state="verified" if sdk_version == EXPECTED_SDK_VERSION else "unverified",
                ),
                PreflightFact(
                    key="cli_version",
                    value=cli_version,
                    state="verified" if cli_version == EXPECTED_CLI_VERSION else "unverified",
                ),
                PreflightFact(
                    key="cli_package_version",
                    value=cli_package_version,
                    state=(
                        "verified" if cli_package_version == EXPECTED_CLI_VERSION else "unverified"
                    ),
                ),
                PreflightFact(
                    key="cli_path",
                    value=cli_path,
                    state="verified" if cli_path is not None else "unverified",
                ),
                PreflightFact(
                    key="cli_sha256",
                    value=cli_hash,
                    state="verified" if cli_hash is not None else "unverified",
                ),
                PreflightFact(
                    key="audited_source_revision",
                    value="ff6aec96948b70d94983af2641a6b67c94faeff5",
                    state="verified",
                ),
            ),
            binding=(
                PreflightFact(key="requested_model", value=spec.model_id, state="verified"),
                PreflightFact(key="requested_effort", value=spec.effort.value, state="verified"),
                PreflightFact(
                    key="effective_model",
                    state="unverified",
                    reason="no fresh Codex thread was created",
                ),
                PreflightFact(
                    key="supported_effort",
                    state="unverified",
                    reason="no account-scoped model availability check was performed",
                ),
                PreflightFact(
                    key="approved_binding_id",
                    value=context.binding_id,
                    state="verified" if context.binding_id else "unverified",
                ),
            ),
            auth=(
                PreflightFact(
                    key="auth_available",
                    state="unverified",
                    reason=(
                        "authentication is checked by Codex during an explicitly authorized "
                        "preparation"
                    ),
                ),
                PreflightFact(key="auth_method", state="unverified"),
            ),
            permissions=(
                PreflightFact(
                    key="requested_sandbox",
                    value=spec.permissions.sandbox.value,
                    state="verified",
                ),
                PreflightFact(
                    key="effective_sandbox",
                    state="unverified",
                    reason="runtime effective configuration was not read",
                ),
                PreflightFact(
                    key="requested_shell_network",
                    value=spec.permissions.shell_network,
                    state="verified",
                ),
                PreflightFact(
                    key="effective_integrations",
                    state="unverified",
                    reason="SDK configuration alone does not prove integrations are disabled",
                ),
            ),
            capabilities=(
                PreflightFact(
                    key="steering",
                    value=False,
                    state="unsupported",
                    reason="steering is disabled in M6",
                ),
                PreflightFact(
                    key="read_only_report_output",
                    value=EXPECTED_OUTPUT_SCHEMA,
                    state="unverified",
                    reason=(
                        "the output body bridge is not yet connected to a provider turn's "
                        "final message"
                    ),
                ),
            ),
            ownership=(
                PreflightFact(
                    key="filesystem_owner",
                    value="codex",
                    state="unverified",
                    reason="OS sandbox ownership is not demonstrated",
                ),
                PreflightFact(
                    key="process_owner",
                    value="adapter",
                    state="unverified",
                    reason="independent process settlement is not demonstrated",
                ),
                PreflightFact(key="workspace_owner", value="service", state="verified"),
                PreflightFact(key="artifact_owner", value="service", state="verified"),
            ),
            provenance=(
                PreflightFact(
                    key="backend_config_sha256",
                    value=config_fingerprint,
                    state="verified",
                ),
                PreflightFact(
                    key="project_path_identity_sha256",
                    value=project_fingerprint,
                    state="verified",
                ),
                PreflightFact(
                    key="dedicated_home_configured",
                    value=dedicated_home,
                    state="verified" if dedicated_home else "unverified",
                ),
                PreflightFact(
                    key="home_identity_sha256",
                    value=home_identity,
                    state="verified" if home else "unverified",
                ),
                PreflightFact(
                    key="environment_policy",
                    value="allowlist-v1",
                    state="unverified",
                    reason=(
                        "the SDK inherits the service environment before applying configured values"
                    ),
                ),
                PreflightFact(
                    key="instruction_source_hashes",
                    state="unverified",
                    reason="project and managed instruction layers were not read",
                ),
            ),
            recovery=(
                PreflightFact(
                    key="owner_generation",
                    state="unverified",
                    reason="no independently verified process owner was created",
                ),
                PreflightFact(
                    key="inspection_semantics",
                    value="exact-retained-thread-only",
                    state="unverified",
                ),
            ),
        )
        return PreflightResult(accepted=False, issues=issues, snapshot=snapshot)

    async def start(
        self,
        spec: AgentRunSpec,
        *,
        preflight_record_id: str | None = None,
        preflight_record_hash: str | None = None,
    ) -> WorkerHandle:
        del preflight_record_id, preflight_record_hash
        raise KnownPrelaunchFailure(
            FailureClass.CONFIGURATION,
            "Codex activation is blocked until host compatibility and preparation checks "
            "are implemented",
            safe_to_retry=False,
        )

    async def events(self, handle: WorkerHandle) -> AsyncIterator[WorkerEvent]:
        yield WorkerDisconnectedEvent(
            attempt_id=handle.attempt_id,
            sequence=1,
            kind=WorkerEventKind.DISCONNECTED,
            reason="Codex attempt has no activated runtime owner",
        )

    async def steer(self, handle: WorkerHandle, command: SteerCommand) -> ControlAck:
        del handle
        return ControlAck(
            command_id=command.command_id,
            accepted=False,
            supported=False,
            reason="Codex steering is unsupported by the M6 adapter",
        )

    async def interrupt(self, handle: WorkerHandle, command_id: UUID) -> ControlAck:
        if handle.backend != "codex" or not handle.thread_id or not handle.turn_id:
            return ControlAck(
                command_id=command_id,
                accepted=False,
                reason="exact thread and turn identity are required for interruption",
            )
        return ControlAck(
            command_id=command_id,
            accepted=False,
            reason="no verified Codex owner is available for exact-turn interruption",
        )

    async def inspect(self, identity: WorkerIdentity) -> Reconciliation:
        return Reconciliation(
            known=False,
            detail=(
                f"Codex owner for attempt {identity.attempt_id} cannot be independently inspected"
            ),
        )

    async def close(self, handle: WorkerHandle) -> ShutdownReceipt:
        del handle
        return ShutdownReceipt(
            settled=False,
            detail="no independent Codex process-owner settlement evidence is available",
        )

    @staticmethod
    def _distribution_version(name: str) -> str | None:
        try:
            return importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            return None

    @staticmethod
    def _is_dedicated_home(value: str) -> bool:
        try:
            candidate = Path(value).expanduser().resolve()
            return candidate.is_absolute() and candidate != Path.home().resolve()
        except OSError:
            return False

    @classmethod
    def _home_identity(cls, value: str) -> str:
        normalized = str(Path(value).expanduser().resolve())
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def _inspect_cli() -> tuple[str | None, str | None, str | None]:
        try:
            candidate = Path(
                str(importlib.resources.files("codex_cli_bin").joinpath("bin", "codex"))
            )
            binary_hash = hashlib.sha256(candidate.read_bytes()).hexdigest()
            result = subprocess.run(
                [str(candidate), "--version"],
                capture_output=True,
                check=True,
                text=True,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError, ModuleNotFoundError, TypeError):
            return None, None, None
        version = result.stdout.strip()
        if not version.startswith("codex-cli "):
            return str(candidate), None, binary_hash
        return str(candidate), version.removeprefix("codex-cli "), binary_hash
