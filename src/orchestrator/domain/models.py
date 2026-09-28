"""Strict application configuration and immutable resolved-domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Identifier = Annotated[str, StringConstraints(min_length=1, pattern=r"^[a-z][a-z0-9_-]*$")]
NonEmpty = Annotated[str, StringConstraints(min_length=1)]


class StrictModel(BaseModel):
    """Base for versioned input models; unknown fields are contract errors."""

    model_config = ConfigDict(extra="forbid", validate_default=True)


class FrozenModel(StrictModel):
    """Immutable base used for resolved specifications and persisted facts."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class Effort(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"
    MAX = "max"
    ULTRA = "ultra"


class SandboxMode(StrEnum):
    READ_ONLY = "read-only"
    WORKSPACE_WRITE = "workspace-write"


class ApprovalMode(StrEnum):
    DENY_ALL = "deny_all"


class PermissionSet(FrozenModel):
    """Requested worker permissions; tool lists remain intentions, not enforcement."""

    sandbox: SandboxMode
    shell_network: bool = False
    web_search: bool = False
    approval_mode: ApprovalMode = ApprovalMode.DENY_ALL
    external_integrations: bool = False
    nested_agents: bool = False

    def is_within(self, ceiling: PermissionSet) -> bool:
        sandbox_ok = (
            self.sandbox == SandboxMode.READ_ONLY or ceiling.sandbox == SandboxMode.WORKSPACE_WRITE
        )
        return (
            sandbox_ok
            and (not self.shell_network or ceiling.shell_network)
            and (not self.web_search or ceiling.web_search)
            and (not self.external_integrations or ceiling.external_integrations)
            and (not self.nested_agents or ceiling.nested_agents)
            and self.approval_mode == ApprovalMode.DENY_ALL
        )


class MemoryPolicy(StrEnum):
    DISABLED = "disabled"


class AgentRole(StrEnum):
    DIAGNOSIS = "diagnosis"
    HANDOFF = "handoff"
    IMPLEMENTATION = "implementation"
    PLANNING = "planning"
    PROTOTYPE = "prototype"
    PROTOTYPE_VALIDATION = "prototype-validation"
    RESEARCH = "research"
    REVIEW = "review"
    SYNTHESIS = "synthesis"
    VALIDATION = "validation"
    VERIFICATION = "verification"


class FailureClass(StrEnum):
    PROVIDER_TRANSIENT = "provider_transient"
    TOOL_TRANSIENT = "tool_transient"
    CONFIGURATION = "configuration"
    POLICY = "policy"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    WORKER_FAILURE = "worker_failure"
    CANCELLED = "cancelled"


class RetryPolicy(FrozenModel):
    max_attempts: int = Field(ge=1, le=10)
    recoverable_classes: tuple[FailureClass, ...]
    require_known_terminal: bool = True
    require_safe_retry: bool = True


class ContextPolicy(FrozenModel):
    id: Identifier
    max_bytes: int = Field(ge=1, le=10_000_000)
    include_full_history: bool = False


class AgentProfile(StrictModel):
    schema_version: Literal[1] = 1
    id: Identifier
    version: NonEmpty
    name: NonEmpty
    role: AgentRole
    objective: NonEmpty
    base_prompt: NonEmpty
    overlay_paths: list[str] = Field(default_factory=list)
    backend: Identifier
    model_binding: Identifier
    effort: Effort
    skills: list[str] = Field(default_factory=list)
    tools: list[Identifier] = Field(default_factory=list)
    permissions: PermissionSet
    context_policy: ContextPolicy
    memory_policy: MemoryPolicy = MemoryPolicy.DISABLED
    timeout_seconds: int = Field(ge=1, le=86_400)
    retry_policy: RetryPolicy
    required_outputs: list[Identifier]
    metadata: dict[str, str] = Field(default_factory=dict)


class AgentCatalog(StrictModel):
    schema_version: Literal[1] = 1
    agents: list[AgentProfile]


class StageKind(StrEnum):
    WORKER = "worker"
    INTEGRATE = "integrate"
    INTEGRATION_CHECK = "integration_check"
    REPAIR_GATE = "repair_gate"


class Condition(StrEnum):
    ALWAYS = "always"
    REPAIR_NEEDED = "repair_needed"
    REPAIR_NOT_NEEDED = "repair_not_needed"


class SlotKind(StrEnum):
    FIXED = "fixed"
    SELECT_ONE = "select_one"
    ELASTIC = "elastic"


class StageCompletion(StrEnum):
    ARTIFACT_READY = "artifact_ready"
    REPORT_PRESENT = "report_present"
    REPORT_PASSED = "report_passed"
    INTEGRATION_SUCCEEDED = "integration_succeeded"
    DECISION_RECORDED = "decision_recorded"


class WorkflowCompletion(StrEnum):
    REPORTS_PRESENT = "reports_present"
    VALIDATED_PROTOTYPE = "validated_prototype"
    VERIFIED_REVISION = "verified_revision"
    VERIFIED_RESEARCH = "verified_research"


class WorkflowStage(StrictModel):
    id: Identifier
    kind: StageKind
    depends_on: list[Identifier] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    required_outputs: list[Identifier]
    when: Condition = Condition.ALWAYS
    optional: bool = False
    completion: StageCompletion
    slot_kind: SlotKind | None = None
    min_workers: int | None = Field(default=None, ge=1, le=32)
    max_workers: int | None = Field(default=None, ge=1, le=32)
    allowed_profiles: list[Identifier] = Field(default_factory=list)
    default_profile: Identifier | None = None
    parallel_group: Identifier | None = None
    slot_briefs: list[NonEmpty] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_stage_shape(self) -> WorkflowStage:
        if self.kind == StageKind.WORKER:
            required = (self.slot_kind, self.min_workers, self.max_workers, self.default_profile)
            if any(value is None for value in required) or not self.allowed_profiles:
                raise ValueError(
                    "worker stages require slot_kind, bounds, profiles, and default_profile"
                )
        elif (
            any(
                value is not None
                for value in (
                    self.slot_kind,
                    self.min_workers,
                    self.max_workers,
                    self.default_profile,
                )
            )
            or self.allowed_profiles
        ):
            raise ValueError("non-worker stages cannot declare worker slot fields")
        if (self.min_workers is None) != (self.max_workers is None):
            raise ValueError("min_workers and max_workers must be specified together")
        if (
            self.min_workers is not None
            and self.max_workers is not None
            and self.min_workers > self.max_workers
        ):
            raise ValueError("min_workers must not exceed max_workers")
        if self.slot_kind == SlotKind.FIXED and self.min_workers != self.max_workers:
            raise ValueError("fixed slots require min_workers == max_workers")
        if self.slot_kind == SlotKind.SELECT_ONE and (self.min_workers, self.max_workers) != (1, 1):
            raise ValueError("select_one slots require exactly one worker")
        if self.default_profile is not None and self.default_profile not in self.allowed_profiles:
            raise ValueError("default_profile must appear in allowed_profiles")
        if self.when == Condition.ALWAYS and self.optional:
            raise ValueError("unconditional optional stages require an explicit skip policy")
        if self.when != Condition.ALWAYS and not self.optional:
            raise ValueError("conditional stages must be marked optional")
        return self


class RedirectRule(StrictModel):
    stage: Identifier
    allowed_profiles: list[Identifier]


class OrchestratorPolicy(StrictModel):
    schema_version: Literal[1] = 1
    allowed_backends: list[Identifier]
    allowed_model_bindings: list[Identifier]
    allow_optional_skip: bool = False
    allow_count_selection: bool = False
    allow_profile_selection: bool = False
    allow_retry: bool = True
    allow_permission_expansion: bool = False
    allow_new_profiles: bool = False
    allow_required_stage_removal: bool = False
    permission_ceiling: PermissionSet | None = None


class WorkflowPreset(StrictModel):
    schema_version: Literal[1] = 1
    id: Identifier
    version: NonEmpty
    name: NonEmpty
    max_parallelism: int = Field(ge=1, le=64)
    max_duration_seconds: int = Field(ge=1, le=604_800)
    max_attempts_per_slot: int = Field(ge=1, le=10)
    max_repair_cycles: int = Field(ge=0, le=10)
    allowed_profiles: list[Identifier]
    completion: WorkflowCompletion
    required_outputs: list[str]
    allowed_redirects: list[RedirectRule] = Field(default_factory=list)
    policy: OrchestratorPolicy
    stages: list[WorkflowStage]
    branch_outputs: dict[str, dict[str, str]] = Field(default_factory=dict)


class WorkspacePolicy(StrictModel):
    write_strategy: Literal["git_worktree", "read_only"] = "git_worktree"
    require_clean_base_for_writes: bool = True
    integrate_into: Literal["run_worktree"] = "run_worktree"
    apply_to_original: bool = False


class ModelBindingSettings(StrictModel):
    backend: Identifier
    model_id: NonEmpty
    allowed_efforts: list[Effort]


class ProjectContextSettings(StrictModel):
    policy: Identifier
    max_bytes: int = Field(ge=1, le=10_000_000)
    include_full_history: bool = False


class ProjectMemorySettings(StrictModel):
    policy: MemoryPolicy = MemoryPolicy.DISABLED


class ProjectConfig(StrictModel):
    schema_version: Literal[1] = 1
    id: Identifier
    name: NonEmpty
    path: NonEmpty
    settings_revision: NonEmpty = "1"
    max_parallelism: int = Field(ge=1, le=64)
    agent_overlay_paths: list[str] = Field(default_factory=list)
    workflow_overlay_paths: list[str] = Field(default_factory=list)
    allowed_workflows: list[Identifier]
    allowed_commands: list[NonEmpty] = Field(default_factory=list)
    workspace: WorkspacePolicy
    models: dict[Identifier, ModelBindingSettings] = Field(default_factory=dict)
    context: ProjectContextSettings
    memory: ProjectMemorySettings = Field(default_factory=ProjectMemorySettings)


class CodexBackendSettings(StrictModel):
    kind: Literal["codex_sdk"]
    sdk_package: Literal["openai-codex"]
    sdk_version: NonEmpty
    cli_source: Literal["sdk_pinned_dependency"]
    client_per_attempt: bool
    auth_owner: Literal["codex"]
    codex_home_env: NonEmpty
    approval_mode: ApprovalMode
    experimental_api: bool
    interrupt_grace_seconds: int = Field(ge=0, le=300)
    shutdown_grace_seconds: int = Field(ge=0, le=300)
    allow_unverified_policy: bool


class FakeBackendSettings(StrictModel):
    kind: Literal["scripted_fake"]
    test_only: Literal[True]
    clock: Literal["manual"]


type BackendConfig = Annotated[
    CodexBackendSettings | FakeBackendSettings,
    Field(discriminator="kind"),
]


class BackendSettings(StrictModel):
    schema_version: Literal[1] = 1
    backends: dict[Identifier, BackendConfig]


class DevelopmentPreset(StrictModel):
    purpose: NonEmpty
    model_recommendation: NonEmpty
    effort: Effort
    sandbox: SandboxMode
    web_search: Literal["disabled", "live"]
    skills: list[str]
    tools: list[str]
    outputs: list[NonEmpty]
    stop: NonEmpty


class DevelopmentConfig(StrictModel):
    schema_version: Literal[1] = 1
    presets: dict[Identifier, DevelopmentPreset]


class ProfileOverlay(StrictModel):
    schema_version: Literal[1] = 1
    profile_id: Identifier
    base_prompt: NonEmpty | None = None
    model_binding: Identifier | None = None
    effort: Effort | None = None
    timeout_seconds: int | None = Field(default=None, ge=1, le=86_400)
    context_policy: ContextPolicy | None = None
    permissions: PermissionSet | None = None

    @model_validator(mode="after")
    def reject_null_patch_values(self) -> ProfileOverlay:
        patch_fields = self.model_fields_set - {"schema_version", "profile_id"}
        if not patch_fields:
            raise ValueError("profile overlay must set at least one field")
        if any(getattr(self, name) is None for name in patch_fields):
            raise ValueError("profile overlay values cannot be null")
        return self


class WorkflowOverlay(StrictModel):
    schema_version: Literal[1] = 1
    workflow_id: Identifier
    worker_counts: dict[Identifier, int] = Field(default_factory=dict)
    default_profiles: dict[Identifier, Identifier] = Field(default_factory=dict)


class ProfileOverlayFile(StrictModel):
    schema_version: Literal[1] = 1
    profiles: list[ProfileOverlay]


class WorkflowOverlayFile(StrictModel):
    schema_version: Literal[1] = 1
    workflows: list[WorkflowOverlay]


class RunOverrides(StrictModel):
    schema_version: Literal[1] = 1
    worker_counts: dict[Identifier, int] = Field(default_factory=dict)
    profile_selections: dict[Identifier, Identifier] = Field(default_factory=dict)
    model_bindings: dict[Identifier, Identifier] = Field(default_factory=dict)
    efforts: dict[Identifier, Effort] = Field(default_factory=dict)
    permissions: dict[Identifier, PermissionSet] = Field(default_factory=dict)


class ResolvedModelBinding(FrozenModel):
    alias: Identifier
    backend: Identifier
    model_id: NonEmpty
    allowed_efforts: tuple[Effort, ...]


class ResolvedProfile(FrozenModel):
    id: Identifier
    version: NonEmpty
    name: NonEmpty
    role: AgentRole
    objective: NonEmpty
    base_prompt: NonEmpty
    backend: Identifier
    model_binding: Identifier
    model_id: NonEmpty
    effort: Effort
    skills: tuple[str, ...]
    tools: tuple[Identifier, ...]
    permissions: PermissionSet
    context_policy: ContextPolicy
    memory_policy: MemoryPolicy
    timeout_seconds: int
    retry_policy: RetryPolicy
    required_outputs: tuple[Identifier, ...]


class ResolvedStage(FrozenModel):
    id: Identifier
    kind: StageKind
    depends_on: tuple[Identifier, ...]
    inputs: tuple[str, ...]
    required_outputs: tuple[Identifier, ...]
    when: Condition
    optional: bool
    completion: StageCompletion
    slot_kind: SlotKind | None
    min_workers: int | None
    max_workers: int | None
    allowed_profiles: tuple[Identifier, ...]
    default_profile: Identifier | None
    parallel_group: Identifier | None
    slot_briefs: tuple[str, ...]


class ResolvedRedirectRule(FrozenModel):
    stage: Identifier
    allowed_profiles: tuple[Identifier, ...]


class ResolvedWorkflow(FrozenModel):
    id: Identifier
    version: NonEmpty
    name: NonEmpty
    max_parallelism: int
    max_duration_seconds: int
    max_attempts_per_slot: int
    max_repair_cycles: int
    allowed_profiles: tuple[Identifier, ...]
    completion: WorkflowCompletion
    required_outputs: tuple[str, ...]
    allowed_redirects: tuple[ResolvedRedirectRule, ...]
    stages: tuple[ResolvedStage, ...]
    branch_outputs: tuple[tuple[str, tuple[tuple[str, str], ...]], ...]


class StageSelection(FrozenModel):
    stage_id: Identifier
    worker_count: int
    profile_ids: tuple[Identifier, ...]


class ProjectSnapshot(FrozenModel):
    project_id: Identifier
    settings_revision: str
    project_path: NonEmpty
    max_parallelism: int
    allowed_commands: tuple[str, ...]
    write_strategy: str
    require_clean_base_for_writes: bool
    integrate_into: str
    apply_to_original: bool
    context_policy: Identifier
    context_max_bytes: int
    include_full_history: bool


class OverrideEntry(FrozenModel):
    path: NonEmpty
    value: str


class RunSpec(FrozenModel):
    schema_version: Literal[1] = 1
    task: NonEmpty
    project: ProjectSnapshot
    workflow: ResolvedWorkflow
    profiles: tuple[ResolvedProfile, ...]
    model_bindings: tuple[ResolvedModelBinding, ...]
    selections: tuple[StageSelection, ...]
    applied_overrides: tuple[OverrideEntry, ...] = ()
    snapshot_hash: str


class InputEntry(FrozenModel):
    name: NonEmpty
    content_hash: str
    source: NonEmpty
    reason: NonEmpty


class AgentRunSpec(FrozenModel):
    schema_version: Literal[1] = 1
    run_id: NonEmpty
    attempt_id: NonEmpty
    parent_attempt_id: str | None = None
    profile_id: Identifier
    profile_version: NonEmpty
    instructions: NonEmpty
    input_manifest: tuple[InputEntry, ...]
    backend: Identifier
    model_id: NonEmpty
    effort: Effort
    permissions: PermissionSet
    skills: tuple[str, ...]
    tools: tuple[Identifier, ...]
    workspace_revision: str | None = None
    run_snapshot_hash: NonEmpty


class RunStatus(StrEnum):
    READY = "ready"
    RUNNING = "running"
    PAUSE_REQUESTED = "pause_requested"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ATTENTION_REQUIRED = "attention_required"


class AttemptStatus(StrEnum):
    PENDING = "pending"
    LAUNCHING = "launching"
    RUNNING = "running"
    CANCEL_REQUESTED = "cancel_requested"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    OUTCOME_UNKNOWN = "outcome_unknown"


class RunState(StrictModel):
    """Mutable projection kept separate from immutable RunSpec."""

    schema_version: Literal[1] = 1
    run_id: NonEmpty
    status: RunStatus
    revision: int = Field(ge=0)
    active_stages: list[Identifier] = Field(default_factory=list)
    attempts_used: int = Field(default=0, ge=0)
    elapsed_seconds: float = Field(default=0, ge=0)


class AttemptState(StrictModel):
    schema_version: Literal[1] = 1
    attempt_id: NonEmpty
    status: AttemptStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    receipt_id: str | None = None
    artifact_ids: list[str] = Field(default_factory=list)
    error_class: FailureClass | None = None
    error_summary: str | None = None


class Artifact(FrozenModel):
    schema_version: Literal[1] = 1
    id: NonEmpty
    attempt_id: NonEmpty
    input_revision: NonEmpty
    workspace_revision: str | None = None
    schema_id: Identifier
    relative_path: NonEmpty
    content_hash: NonEmpty


class Handoff(FrozenModel):
    schema_version: Literal[1] = 1
    source_attempt_id: NonEmpty
    destination_stage: Identifier
    destination_slot: NonEmpty
    input_revision: NonEmpty
    content_hash: NonEmpty
    project_revision: str | None = None
    schema_id: Identifier
    relative_path: NonEmpty


class InterventionKind(StrEnum):
    PAUSE = "pause"
    RESUME = "resume"
    STOP = "stop"
    STOP_ATTEMPT = "stop_attempt"
    STEER = "steer"
    RETRY = "retry"
    REDIRECT = "redirect"


class InterventionBase(FrozenModel):
    schema_version: Literal[1] = 1
    command_id: UUID
    actor: NonEmpty
    target: NonEmpty
    expected_run_revision: int = Field(ge=0)


class PauseIntervention(InterventionBase):
    kind: Literal[InterventionKind.PAUSE]


class ResumeIntervention(InterventionBase):
    kind: Literal[InterventionKind.RESUME]


class StopIntervention(InterventionBase):
    kind: Literal[InterventionKind.STOP]


class StopAttemptIntervention(InterventionBase):
    kind: Literal[InterventionKind.STOP_ATTEMPT]
    attempt_id: NonEmpty


class SteerIntervention(InterventionBase):
    kind: Literal[InterventionKind.STEER]
    attempt_id: NonEmpty
    expected_turn_id: NonEmpty
    instruction: NonEmpty


class RetryIntervention(InterventionBase):
    kind: Literal[InterventionKind.RETRY]
    attempt_id: NonEmpty


class RedirectIntervention(InterventionBase):
    kind: Literal[InterventionKind.REDIRECT]
    stage_id: Identifier
    recipient_profile_id: Identifier


type Intervention = Annotated[
    PauseIntervention
    | ResumeIntervention
    | StopIntervention
    | StopAttemptIntervention
    | SteerIntervention
    | RetryIntervention
    | RedirectIntervention,
    Field(discriminator="kind"),
]


class EventKind(StrEnum):
    RUN_STATUS_CHANGED = "run_status_changed"
    ATTEMPT_STATUS_CHANGED = "attempt_status_changed"
    INTERVENTION_REQUESTED = "intervention_requested"
    INTERVENTION_DELIVERED = "intervention_delivered"
    ARTIFACT_RECORDED = "artifact_recorded"
    HANDOFF_RECORDED = "handoff_recorded"


class EventBase(FrozenModel):
    schema_version: Literal[1] = 1
    event_id: UUID
    run_id: NonEmpty
    sequence: int | None = Field(default=None, ge=1)
    occurred_at: datetime
    actor: NonEmpty
    cause_event_id: UUID | None = None


class RunStatusChangedEvent(EventBase):
    kind: Literal[EventKind.RUN_STATUS_CHANGED]
    previous: RunStatus | None = None
    current: RunStatus
    reason: str | None = None


class AttemptStatusChangedEvent(EventBase):
    kind: Literal[EventKind.ATTEMPT_STATUS_CHANGED]
    attempt_id: NonEmpty
    previous: AttemptStatus | None = None
    current: AttemptStatus
    reason: str | None = None


class InterventionRequestedEvent(EventBase):
    kind: Literal[EventKind.INTERVENTION_REQUESTED]
    intervention: Intervention


class InterventionDeliveredEvent(EventBase):
    kind: Literal[EventKind.INTERVENTION_DELIVERED]
    command_id: UUID
    delivery_status: Literal["acknowledged", "rejected", "unknown"]
    result: str | None = None


class ArtifactRecordedEvent(EventBase):
    kind: Literal[EventKind.ARTIFACT_RECORDED]
    artifact: Artifact


class HandoffRecordedEvent(EventBase):
    kind: Literal[EventKind.HANDOFF_RECORDED]
    handoff: Handoff


type Event = Annotated[
    RunStatusChangedEvent
    | AttemptStatusChangedEvent
    | InterventionRequestedEvent
    | InterventionDeliveredEvent
    | ArtifactRecordedEvent
    | HandoffRecordedEvent,
    Field(discriminator="kind"),
]
