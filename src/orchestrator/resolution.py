"""Pure project/run overlay resolution and immutable snapshot hashing."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping, Sequence

from pydantic import BaseModel

from orchestrator.domain.decisions import ResolvedDecisionQuestion
from orchestrator.domain.models import (
    AgentProfile,
    ContextPolicy,
    Effort,
    OverrideEntry,
    ProfileOverlay,
    ProjectConfig,
    ProjectSnapshot,
    ResolvedModelBinding,
    ResolvedOrchestratorPolicy,
    ResolvedProfile,
    ResolvedRedirectRule,
    ResolvedStage,
    ResolvedWorkflow,
    RunOverrides,
    RunSpec,
    SlotKind,
    StageKind,
    StageSelection,
    WorkflowOverlay,
    WorkflowPreset,
)


class ResolutionError(ValueError):
    """A missing, unsupported, or unsafe run setting with its source path."""


ModelAvailability = Mapping[str, Mapping[str, Collection[Effort | str]]]


def canonical_snapshot_bytes(model: BaseModel) -> bytes:
    """Canonical JSON bytes for a resolved specification, excluding its hash field."""
    data = model.model_dump(mode="json", exclude={"snapshot_hash"}, exclude_none=False)
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def snapshot_hash(model: BaseModel) -> str:
    return hashlib.sha256(canonical_snapshot_bytes(model)).hexdigest()


def resolve_run(
    task: str,
    project: ProjectConfig,
    workflow: WorkflowPreset,
    profiles: Sequence[AgentProfile],
    *,
    model_availability: ModelAvailability | None,
    profile_overlays: Sequence[ProfileOverlay] = (),
    workflow_overlays: Sequence[WorkflowOverlay] = (),
    overrides: RunOverrides | None = None,
    settings_revision: str | None = None,
) -> RunSpec:
    """Resolve all worker choices without I/O, clocks, or provider discovery."""
    if not task.strip():
        raise ResolutionError("task: must not be blank")
    if workflow.id not in project.allowed_workflows:
        raise ResolutionError(f"project.allowed_workflows: {workflow.id!r} is not allowed")
    if model_availability is None:
        raise ResolutionError("model_availability: deterministic backend availability is required")

    run_overrides = overrides or RunOverrides()
    profile_map = {profile.id: profile for profile in profiles}
    applied: list[OverrideEntry] = []
    for profile_index, profile_overlay in enumerate(profile_overlays):
        if profile_overlay.profile_id not in profile_map:
            raise ResolutionError(
                f"profile_overlays.{profile_index}.profile_id: unknown profile "
                f"{profile_overlay.profile_id!r}"
            )
    for workflow_index, workflow_overlay in enumerate(workflow_overlays):
        if workflow_overlay.workflow_id != workflow.id:
            raise ResolutionError(
                f"workflow_overlays.{workflow_index}.workflow_id: expected {workflow.id!r}, "
                f"got {workflow_overlay.workflow_id!r}"
            )

    overlaid_profiles = {
        profile_id: _apply_profile_overlays(profile, profile_overlays, workflow, applied)
        for profile_id, profile in profile_map.items()
    }
    resolved_workflow = _apply_workflow_overlays(workflow, workflow_overlays, applied)
    for stage in resolved_workflow.stages:
        for profile_id in stage.allowed_profiles:
            profile = overlaid_profiles.get(profile_id)
            if profile and profile.timeout_seconds > workflow.max_duration_seconds:
                raise ResolutionError(
                    f"workflow.stages.{stage.id}.profiles.{profile_id}.timeout_seconds: "
                    "profile timeout exceeds workflow wall-time limit"
                )

    allowed_stages = {stage.id: stage for stage in resolved_workflow.stages}
    for stage_id in run_overrides.worker_counts:
        if stage_id not in allowed_stages:
            raise ResolutionError(f"overrides.worker_counts.{stage_id}: unknown stage")
    for stage_id in run_overrides.profile_selections:
        if stage_id not in allowed_stages:
            raise ResolutionError(f"overrides.profile_selections.{stage_id}: unknown stage")

    selections: list[StageSelection] = []
    selected_profile_ids: set[str] = set()
    for stage in resolved_workflow.stages:
        if stage.kind != StageKind.WORKER:
            continue
        assert stage.min_workers is not None and stage.max_workers is not None
        assert stage.slot_kind is not None and stage.default_profile is not None
        overlay_count = _overlay_count_for_stage(stage.id, workflow_overlays)
        requested_count = run_overrides.worker_counts.get(stage.id, overlay_count)
        if (
            requested_count is not None
            and stage.slot_kind.value != "elastic"
            and requested_count != stage.min_workers
        ):
            raise ResolutionError(
                f"overrides.worker_counts.{stage.id}: only elastic slots can change count"
            )
        if stage.id in run_overrides.worker_counts and not workflow.policy.allow_count_selection:
            raise ResolutionError(
                f"overrides.worker_counts.{stage.id}: count selection is forbidden by policy"
            )
        count = stage.min_workers if requested_count is None else requested_count
        if not stage.min_workers <= count <= stage.max_workers:
            raise ResolutionError(
                f"overrides.worker_counts.{stage.id}: {count} is outside "
                f"[{stage.min_workers}, {stage.max_workers}]"
            )
        effective_parallelism = min(workflow.max_parallelism, project.max_parallelism)
        if count > effective_parallelism:
            raise ResolutionError(
                f"stages.{stage.id}.worker_count: {count} exceeds effective concurrency cap "
                f"{effective_parallelism}"
            )

        selected_profile = stage.default_profile
        if stage.id in run_overrides.profile_selections:
            if not workflow.policy.allow_profile_selection:
                raise ResolutionError(
                    f"overrides.profile_selections.{stage.id}: selection is forbidden by policy"
                )
            selected_profile = run_overrides.profile_selections[stage.id]
        if selected_profile not in stage.allowed_profiles:
            raise ResolutionError(
                f"overrides.profile_selections.{stage.id}: {selected_profile!r} "
                "is outside the stage allowlist"
            )
        if selected_profile not in overlaid_profiles:
            raise ResolutionError(
                f"stages.{stage.id}.profile: unknown profile {selected_profile!r}"
            )
        selected_profile_ids.add(selected_profile)
        selections.append(
            StageSelection(
                stage_id=stage.id,
                worker_count=count,
                profile_ids=tuple(selected_profile for _ in range(count)),
            )
        )
        if count != stage.min_workers:
            applied.append(OverrideEntry(path=f"stage.{stage.id}.worker_count", value=str(count)))
        if stage.id in run_overrides.profile_selections:
            applied.append(OverrideEntry(path=f"stage.{stage.id}.profile", value=selected_profile))

    for key in (
        *run_overrides.model_bindings,
        *run_overrides.efforts,
        *run_overrides.permissions,
    ):
        if key not in selected_profile_ids:
            raise ResolutionError(
                f"overrides.{key}: profile is not selected by this resolved workflow"
            )

    redirect_profile_ids = {
        profile_id for rule in workflow.allowed_redirects for profile_id in rule.allowed_profiles
    }
    resolved_profiles: list[ResolvedProfile] = []
    resolved_bindings: dict[tuple[str, str], ResolvedModelBinding] = {}
    for profile_id in sorted(selected_profile_ids | redirect_profile_ids):
        profile = overlaid_profiles[profile_id]
        model_alias = run_overrides.model_bindings.get(profile_id, profile.model_binding)
        effort = run_overrides.efforts.get(profile_id, profile.effort)
        permissions = run_overrides.permissions.get(profile_id, profile.permissions)
        base_profile = profile_map[profile_id]
        ceiling = workflow.policy.permission_ceiling or base_profile.permissions
        if not permissions.is_within(ceiling):
            raise ResolutionError(
                f"overrides.permissions.{profile_id}: permission widening exceeds "
                "the profile/policy ceiling"
            )
        if not permissions.is_within(profile.permissions):
            raise ResolutionError(
                f"overrides.permissions.{profile_id}: permission widening is forbidden"
            )
        if model_alias not in workflow.policy.allowed_model_bindings:
            raise ResolutionError(
                f"overrides.model_bindings.{profile_id}: binding {model_alias!r} "
                "is forbidden by policy"
            )
        binding = project.models.get(model_alias)
        if binding is None:
            raise ResolutionError(
                f"project.models.{model_alias}: required model binding for "
                f"profile {profile_id!r} is missing"
            )
        if binding.backend != profile.backend:
            raise ResolutionError(
                f"project.models.{model_alias}.backend: expected {profile.backend!r}, "
                f"got {binding.backend!r}"
            )
        if effort not in binding.allowed_efforts:
            raise ResolutionError(
                f"project.models.{model_alias}.allowed_efforts: does not include {effort.value!r}"
            )
        backend_models = model_availability.get(profile.backend)
        if backend_models is None:
            raise ResolutionError(
                f"model_availability.{profile.backend}: backend availability is missing"
            )
        available_efforts = backend_models.get(binding.model_id)
        if available_efforts is None:
            raise ResolutionError(
                f"model_availability.{profile.backend}.{binding.model_id}: model is unavailable"
            )
        normalized_efforts = {Effort(value) for value in available_efforts}
        if effort not in normalized_efforts:
            raise ResolutionError(
                f"model_availability.{profile.backend}.{binding.model_id}: unsupported effort "
                f"{effort.value!r}"
            )
        if profile.context_policy.id != project.context.policy:
            raise ResolutionError(
                f"project.context.policy: {project.context.policy!r} is not compatible with "
                f"profile {profile_id!r} policy {profile.context_policy.id!r}"
            )
        effective_context = ContextPolicy(
            id=profile.context_policy.id,
            max_bytes=min(profile.context_policy.max_bytes, project.context.max_bytes),
            include_full_history=(
                profile.context_policy.include_full_history and project.context.include_full_history
            ),
        )

        resolved_profiles.append(
            ResolvedProfile(
                id=profile.id,
                version=profile.version,
                name=profile.name,
                role=profile.role,
                objective=profile.objective,
                base_prompt=profile.base_prompt,
                backend=profile.backend,
                model_binding=model_alias,
                model_id=binding.model_id,
                effort=effort,
                skills=tuple(profile.skills),
                tools=tuple(profile.tools),
                permissions=permissions,
                context_policy=effective_context,
                memory_policy=profile.memory_policy,
                timeout_seconds=profile.timeout_seconds,
                retry_policy=profile.retry_policy,
                required_outputs=tuple(profile.required_outputs),
            )
        )
        resolved_bindings[(profile.backend, binding.model_id)] = ResolvedModelBinding(
            alias=model_alias,
            backend=profile.backend,
            model_id=binding.model_id,
            allowed_efforts=tuple(binding.allowed_efforts),
        )
        if model_alias != profile.model_binding:
            applied.append(
                OverrideEntry(path=f"profile.{profile_id}.model_binding", value=model_alias)
            )
        if effort != profile.effort:
            applied.append(OverrideEntry(path=f"profile.{profile_id}.effort", value=effort.value))

    resolved_workflow_model = _freeze_workflow(resolved_workflow, project.max_parallelism)
    project_snapshot = ProjectSnapshot(
        project_id=project.id,
        settings_revision=settings_revision or project.settings_revision,
        project_path=project.path,
        max_parallelism=project.max_parallelism,
        allowed_commands=tuple(project.allowed_commands),
        write_strategy=project.workspace.write_strategy,
        require_clean_base_for_writes=project.workspace.require_clean_base_for_writes,
        integrate_into=project.workspace.integrate_into,
        apply_to_original=project.workspace.apply_to_original,
        context_policy=project.context.policy,
        context_max_bytes=project.context.max_bytes,
        include_full_history=project.context.include_full_history,
    )
    provisional = RunSpec(
        task=task,
        project=project_snapshot,
        workflow=resolved_workflow_model,
        profiles=tuple(resolved_profiles),
        model_bindings=tuple(
            sorted(
                resolved_bindings.values(),
                key=lambda item: (item.backend, item.alias, item.model_id),
            )
        ),
        selections=tuple(selections),
        applied_overrides=tuple(sorted(applied, key=lambda item: (item.path, item.value))),
        snapshot_hash="pending",
    )
    return provisional.model_copy(update={"snapshot_hash": snapshot_hash(provisional)})


def _apply_profile_overlays(
    profile: AgentProfile,
    overlays: Sequence[ProfileOverlay],
    workflow: WorkflowPreset,
    applied: list[OverrideEntry],
) -> AgentProfile:
    current = profile
    for index, overlay in enumerate(overlays):
        if overlay.profile_id != profile.id:
            continue
        fields = overlay.model_dump(exclude_unset=True, exclude={"schema_version", "profile_id"})
        if overlay.permissions is not None:
            ceiling = workflow.policy.permission_ceiling or profile.permissions
            if not overlay.permissions.is_within(
                profile.permissions
            ) or not overlay.permissions.is_within(ceiling):
                raise ResolutionError(
                    f"profile_overlays.{index}.{profile.id}.permissions: "
                    "permission widening is forbidden"
                )
        changes = {key: value for key, value in fields.items() if value is not None}
        if changes:
            current = current.model_copy(update=changes)
            for key, value in changes.items():
                if getattr(profile, key) != value:
                    rendered = value.value if isinstance(value, Effort) else str(value)
                    applied.append(
                        OverrideEntry(path=f"profile.{profile.id}.{key}", value=rendered)
                    )
    return current


def _apply_workflow_overlays(
    workflow: WorkflowPreset,
    overlays: Sequence[WorkflowOverlay],
    applied: list[OverrideEntry],
) -> WorkflowPreset:
    stages = {stage.id: stage for stage in workflow.stages}
    for index, overlay in enumerate(overlays):
        for stage_id, count in overlay.worker_counts.items():
            stage = stages.get(stage_id)
            if stage is None or stage.kind != StageKind.WORKER:
                raise ResolutionError(
                    f"workflow_overlays.{index}.worker_counts.{stage_id}: unknown worker stage"
                )
            assert stage.min_workers is not None and stage.max_workers is not None
            if not stage.min_workers <= count <= stage.max_workers:
                raise ResolutionError(
                    f"workflow_overlays.{index}.worker_counts.{stage_id}: {count} is outside "
                    "declared bounds"
                )
            if stage.slot_kind != SlotKind.ELASTIC and count != stage.min_workers:
                raise ResolutionError(
                    f"workflow_overlays.{index}.worker_counts.{stage_id}: "
                    "only elastic counts may change"
                )
            if count != stage.min_workers and not workflow.policy.allow_count_selection:
                raise ResolutionError(
                    f"workflow_overlays.{index}.worker_counts.{stage_id}: "
                    "count selection is forbidden"
                )
            applied.append(
                OverrideEntry(
                    path=f"workflow.{workflow.id}.{stage_id}.worker_count", value=str(count)
                )
            )
        for stage_id, profile_id in overlay.default_profiles.items():
            stage = stages.get(stage_id)
            if stage is None or stage.kind != StageKind.WORKER:
                raise ResolutionError(
                    f"workflow_overlays.{index}.default_profiles.{stage_id}: unknown worker stage"
                )
            if profile_id not in stage.allowed_profiles:
                raise ResolutionError(
                    f"workflow_overlays.{index}.default_profiles.{stage_id}: "
                    "profile is outside stage allowlist"
                )
            if len(stage.allowed_profiles) > 1 and not workflow.policy.allow_profile_selection:
                raise ResolutionError(
                    f"workflow_overlays.{index}.default_profiles.{stage_id}: "
                    "profile selection is forbidden"
                )
            stages[stage_id] = stage.model_copy(update={"default_profile": profile_id})
            applied.append(
                OverrideEntry(
                    path=f"workflow.{workflow.id}.{stage_id}.default_profile", value=profile_id
                )
            )
    return workflow.model_copy(update={"stages": list(stages.values())})


def _overlay_count_for_stage(stage_id: str, overlays: Sequence[WorkflowOverlay]) -> int | None:
    count: int | None = None
    for overlay in overlays:
        if stage_id in overlay.worker_counts:
            count = overlay.worker_counts[stage_id]
    return count


def _freeze_workflow(workflow: WorkflowPreset, project_parallelism: int) -> ResolvedWorkflow:
    return ResolvedWorkflow(
        id=workflow.id,
        version=workflow.version,
        name=workflow.name,
        max_parallelism=min(workflow.max_parallelism, project_parallelism),
        max_duration_seconds=workflow.max_duration_seconds,
        max_attempts_per_slot=workflow.max_attempts_per_slot,
        max_repair_cycles=workflow.max_repair_cycles,
        allowed_profiles=tuple(workflow.allowed_profiles),
        completion=workflow.completion,
        required_outputs=tuple(workflow.required_outputs),
        policy=ResolvedOrchestratorPolicy(
            allowed_backends=tuple(workflow.policy.allowed_backends),
            allowed_model_bindings=tuple(workflow.policy.allowed_model_bindings),
            allow_optional_skip=workflow.policy.allow_optional_skip,
            allow_count_selection=workflow.policy.allow_count_selection,
            allow_profile_selection=workflow.policy.allow_profile_selection,
            allow_retry=workflow.policy.allow_retry,
            allow_permission_expansion=workflow.policy.allow_permission_expansion,
            allow_new_profiles=workflow.policy.allow_new_profiles,
            allow_required_stage_removal=workflow.policy.allow_required_stage_removal,
            permission_ceiling=workflow.policy.permission_ceiling,
            decision_questions=tuple(
                ResolvedDecisionQuestion.model_validate(question.model_dump())
                for question in workflow.policy.decision_questions
            ),
        ),
        allowed_redirects=tuple(
            ResolvedRedirectRule(stage=rule.stage, allowed_profiles=tuple(rule.allowed_profiles))
            for rule in workflow.allowed_redirects
        ),
        stages=tuple(
            ResolvedStage(
                id=stage.id,
                kind=stage.kind,
                depends_on=tuple(stage.depends_on),
                inputs=tuple(stage.inputs),
                required_outputs=tuple(stage.required_outputs),
                when=stage.when,
                optional=stage.optional,
                completion=stage.completion,
                slot_kind=stage.slot_kind,
                min_workers=stage.min_workers,
                max_workers=stage.max_workers,
                allowed_profiles=tuple(stage.allowed_profiles),
                default_profile=stage.default_profile,
                parallel_group=stage.parallel_group,
                slot_briefs=tuple(stage.slot_briefs),
            )
            for stage in workflow.stages
        ),
        branch_outputs=tuple(
            (branch, tuple(sorted(outputs.items())))
            for branch, outputs in sorted(workflow.branch_outputs.items())
        ),
    )
