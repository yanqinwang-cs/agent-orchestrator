"""Static cross-reference and safety validation for shipped configuration."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from orchestrator.domain.models import (
    AgentCatalog,
    AgentProfile,
    AgentRole,
    BackendSettings,
    Condition,
    ProjectConfig,
    SlotKind,
    StageCompletion,
    StageKind,
    WorkflowCompletion,
    WorkflowPreset,
    WorkflowStage,
)


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ConfigValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue | str]) -> None:
        self.issues = tuple(str(issue) for issue in issues)
        super().__init__("\n".join(self.issues))


def _reference_parts(reference: str) -> tuple[str, str] | None:
    source, separator, output = reference.partition(".")
    if not separator or not source or not output:
        return None
    return source, output


def validate_application(
    catalog: AgentCatalog,
    workflows: Iterable[WorkflowPreset],
    backends: BackendSettings,
    project: ProjectConfig | None = None,
) -> None:
    issues: list[ValidationIssue] = []
    profiles: dict[str, AgentProfile] = {}
    for index, profile in enumerate(catalog.agents):
        path = f"agents.{index}.id"
        if profile.id in profiles:
            issues.append(ValidationIssue(path, f"duplicate AgentProfile ID {profile.id!r}"))
        profiles[profile.id] = profile
        if profile.backend not in backends.backends:
            issues.append(
                ValidationIssue(f"agents.{profile.id}.backend", "backend is not configured")
            )

    workflow_list = tuple(workflows)
    workflow_by_id: dict[str, WorkflowPreset] = {}
    for workflow in workflow_list:
        if workflow.id in workflow_by_id:
            issues.append(ValidationIssue(f"workflows.{workflow.id}.id", "duplicate workflow ID"))
        workflow_by_id[workflow.id] = workflow

    for workflow in workflow_list:
        _validate_workflow(workflow, profiles, backends, issues)

    if project is not None:
        for workflow_id in project.allowed_workflows:
            if workflow_id not in workflow_by_id:
                issues.append(
                    ValidationIssue(
                        f"project.allowed_workflows.{workflow_id}", "workflow ID is not available"
                    )
                )
        for alias, binding in project.models.items():
            if binding.backend not in backends.backends:
                issues.append(
                    ValidationIssue(f"project.models.{alias}.backend", "backend is not configured")
                )
    if issues:
        raise ConfigValidationError(issues)


def _validate_workflow(
    workflow: WorkflowPreset,
    profiles: dict[str, AgentProfile],
    backends: BackendSettings,
    issues: list[ValidationIssue],
) -> None:
    base = f"workflows.{workflow.id}"
    stages: dict[str, WorkflowStage] = {}
    for stage in workflow.stages:
        path = f"{base}.stages.{stage.id}"
        if stage.id in stages:
            issues.append(ValidationIssue(path, "duplicate stage ID"))
        stages[stage.id] = stage
        if (
            stage.optional
            and stage.when == Condition.ALWAYS
            and not workflow.policy.allow_optional_skip
        ):
            issues.append(
                ValidationIssue(
                    f"{base}.stages.{stage.id}.optional",
                    "unconditional optional stage requires allow_optional_skip",
                )
            )
        for dependency in stage.depends_on:
            if dependency not in {candidate.id for candidate in workflow.stages}:
                issues.append(
                    ValidationIssue(f"{path}.depends_on", f"unknown stage {dependency!r}")
                )

        if stage.kind == StageKind.WORKER:
            assert stage.min_workers is not None and stage.max_workers is not None
            assert stage.slot_kind is not None and stage.default_profile is not None
            if stage.max_workers > workflow.max_parallelism:
                issues.append(
                    ValidationIssue(
                        f"{path}.max_workers", "slot maximum exceeds workflow max_parallelism"
                    )
                )
            if stage.slot_kind == SlotKind.ELASTIC and stage.min_workers < stage.max_workers:
                if not workflow.policy.allow_count_selection:
                    issues.append(
                        ValidationIssue(
                            f"{base}.policy.allow_count_selection",
                            f"elastic stage {stage.id!r} requires count selection",
                        )
                    )
            if stage.slot_kind == SlotKind.SELECT_ONE and len(stage.allowed_profiles) > 1:
                if not workflow.policy.allow_profile_selection:
                    issues.append(
                        ValidationIssue(
                            f"{base}.policy.allow_profile_selection",
                            f"select-one stage {stage.id!r} requires profile selection",
                        )
                    )
            for profile_id in stage.allowed_profiles:
                profile = profiles.get(profile_id)
                if profile is None:
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles", f"unknown profile {profile_id!r}"
                        )
                    )
                    continue
                if not set(stage.required_outputs) <= set(profile.required_outputs):
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles.{profile_id}.required_outputs",
                            "profile cannot produce every stage-required output",
                        )
                    )
                if profile_id not in workflow.allowed_profiles:
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles",
                            f"{profile_id!r} is outside workflow allowed_profiles",
                        )
                    )
                _validate_profile_policy(profile, workflow, backends, issues)
                if profile.retry_policy.max_attempts > workflow.max_attempts_per_slot:
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles.{profile_id}.retry_policy.max_attempts",
                            "profile retry maximum exceeds workflow max_attempts_per_slot",
                        )
                    )
                if profile.timeout_seconds > workflow.max_duration_seconds:
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles.{profile_id}.timeout_seconds",
                            "profile timeout exceeds workflow max_duration_seconds",
                        )
                    )
        elif stage.kind == StageKind.REPAIR_GATE:
            if stage.completion != StageCompletion.DECISION_RECORDED:
                issues.append(
                    ValidationIssue(f"{path}.completion", "repair_gate must record a decision")
                )
        elif stage.kind in (StageKind.INTEGRATE, StageKind.INTEGRATION_CHECK):
            if stage.completion != StageCompletion.INTEGRATION_SUCCEEDED:
                issues.append(
                    ValidationIssue(
                        f"{path}.completion",
                        "integration stages must require successful integration",
                    )
                )

    allowed = set(workflow.allowed_profiles)
    for profile_id in workflow.allowed_profiles:
        if profile_id not in profiles:
            issues.append(
                ValidationIssue(f"{base}.allowed_profiles", f"unknown profile {profile_id!r}")
            )

    if workflow.policy.allow_permission_expansion:
        issues.append(
            ValidationIssue(
                f"{base}.policy.allow_permission_expansion",
                "v1 does not permit permission expansion",
            )
        )
    if workflow.policy.allow_new_profiles or workflow.policy.allow_required_stage_removal:
        issues.append(
            ValidationIssue(
                f"{base}.policy", "v1 does not permit new profiles or required-stage removal"
            )
        )
    if workflow.policy.permission_ceiling is not None:
        for profile_id in allowed:
            profile = profiles.get(profile_id)
            if profile and not profile.permissions.is_within(workflow.policy.permission_ceiling):
                issues.append(
                    ValidationIssue(
                        f"{base}.policy.permission_ceiling",
                        f"permission ceiling is lower than profile {profile_id!r} permissions",
                    )
                )

    stage_ids = set(stages)
    ancestry: dict[str, set[str]] = {}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> set[str]:
        if stage_id in visiting:
            issues.append(
                ValidationIssue(f"{base}.stages.{stage_id}.depends_on", "dependency cycle")
            )
            return set()
        if stage_id in visited:
            return ancestry.get(stage_id, set())
        visiting.add(stage_id)
        stage = stages[stage_id]
        result: set[str] = set()
        for dependency in stage.depends_on:
            if dependency in stage_ids:
                result.add(dependency)
                result.update(visit(dependency))
        visiting.remove(stage_id)
        visited.add(stage_id)
        ancestry[stage_id] = result
        return result

    for stage_id in sorted(stage_ids):
        visit(stage_id)

    redirect_by_stage = {item.stage: item for item in workflow.allowed_redirects}
    question_ids: set[str] = set()
    decision_stage_ids: set[str] = set()
    for question in workflow.policy.decision_questions:
        path = f"{base}.policy.decision_questions.{question.question_id}"
        if question.question_id in question_ids:
            issues.append(ValidationIssue(path, "duplicate decision question ID"))
        question_ids.add(question.question_id)
        if question.stage_id in decision_stage_ids:
            issues.append(
                ValidationIssue(path + ".stage_id", "only one redirect decision per stage")
            )
        decision_stage_ids.add(question.stage_id)
        decision_stage = stages.get(question.stage_id)
        if (
            decision_stage is None
            or decision_stage.kind != StageKind.WORKER
            or decision_stage.slot_kind != SlotKind.SELECT_ONE
        ):
            issues.append(
                ValidationIssue(
                    path + ".stage_id", "redirect decision requires a select_one worker stage"
                )
            )
            continue
        if not workflow.policy.allow_profile_selection:
            issues.append(
                ValidationIssue(path, "redirect decision requires allow_profile_selection")
            )
        redirect = redirect_by_stage.get(decision_stage.id)
        if redirect is None:
            issues.append(
                ValidationIssue(
                    path, "redirect decision requires a declared allowed_redirects entry"
                )
            )
        else:
            candidates = set(redirect.allowed_profiles)
            if len(candidates) > 16:
                issues.append(
                    ValidationIssue(path, "decision outcome set cannot exceed 16 candidates")
                )
            acceptance = question.acceptance_policy
            if acceptance.fallback_outcome_id is not None and (
                acceptance.fallback_outcome_id not in candidates
            ):
                issues.append(
                    ValidationIssue(
                        path + ".acceptance_policy.fallback_outcome_id",
                        "fallback outcome is outside the declared redirect candidates",
                    )
                )
        for requirement in question.evidence_requirements:
            if requirement.kind == "run_task":
                continue
            source_id = requirement.stage_id
            output_name = requirement.output_name
            evidence_source = stages.get(source_id or "")
            if evidence_source is None or output_name not in evidence_source.required_outputs:
                issues.append(
                    ValidationIssue(
                        path + ".evidence_requirements",
                        f"unknown required stage output {requirement.source_ref!r}",
                    )
                )
            elif source_id not in ancestry.get(decision_stage.id, set()):
                issues.append(
                    ValidationIssue(
                        path + ".evidence_requirements",
                        f"evidence producer {source_id!r} is not an ancestor of the decision stage",
                    )
                )

    output_refs: set[str] = set()
    for stage in workflow.stages:
        output_refs.update(f"{stage.id}.{output}" for output in stage.required_outputs)

    branches = workflow.branch_outputs
    branch_names = set(branches)
    conditions_used = {stage.when for stage in workflow.stages if stage.when != Condition.ALWAYS}
    if conditions_used and not branch_names:
        issues.append(
            ValidationIssue(
                f"{base}.branch_outputs", "conditional stages require declared branch outputs"
            )
        )
    if conditions_used and branch_names != {
        Condition.REPAIR_NEEDED.value,
        Condition.REPAIR_NOT_NEEDED.value,
    }:
        issues.append(
            ValidationIssue(
                f"{base}.branch_outputs",
                "repair conditions require both repair_needed and repair_not_needed branches",
            )
        )
    branch_keys = [set(values) for values in branches.values()]
    if branch_keys and any(keys != branch_keys[0] for keys in branch_keys[1:]):
        issues.append(
            ValidationIssue(f"{base}.branch_outputs", "all branches must bind the same output keys")
        )
    for branch, bindings in branches.items():
        branch_condition = next(
            (condition for condition in Condition if condition.value == branch), None
        )
        if branch not in {
            condition.value for condition in Condition if condition != Condition.ALWAYS
        }:
            issues.append(
                ValidationIssue(f"{base}.branch_outputs.{branch}", "undeclared condition")
            )
        for key, reference in bindings.items():
            if reference not in output_refs:
                issues.append(
                    ValidationIssue(
                        f"{base}.branch_outputs.{branch}.{key}",
                        f"unknown output binding {reference!r}",
                    )
                )
            parts = _reference_parts(reference)
            source_stage = stages.get(parts[0]) if parts else None
            if (
                source_stage is not None
                and branch_condition is not None
                and source_stage.when not in {Condition.ALWAYS, branch_condition}
            ):
                issues.append(
                    ValidationIssue(
                        f"{base}.branch_outputs.{branch}.{key}",
                        f"source stage {source_stage.id!r} is inactive in this branch",
                    )
                )

    for stage in workflow.stages:
        path = f"{base}.stages.{stage.id}"
        ancestors = ancestry.get(stage.id, set())
        for reference in stage.inputs:
            if reference in {"task", "project.revision"}:
                continue
            parts = _reference_parts(reference)
            if parts is None:
                issues.append(
                    ValidationIssue(f"{path}.inputs", f"invalid input binding {reference!r}")
                )
                continue
            source, output = parts
            if source == "selected":
                if not branches or any(output not in values for values in branches.values()):
                    issues.append(
                        ValidationIssue(
                            f"{path}.inputs",
                            f"selected binding {reference!r} is not bound in every branch",
                        )
                    )
                else:
                    for branch, values in branches.items():
                        _check_source_binding(
                            f"{base}.branch_outputs.{branch}.{output}",
                            values[output],
                            ancestors,
                            stages,
                            issues,
                        )
            else:
                if source not in ancestors:
                    issues.append(
                        ValidationIssue(
                            f"{path}.inputs", f"producer stage {source!r} is not a dependency"
                        )
                    )
                source_stage = stages.get(source)
                branches_to_check = tuple(branches) or ("always",)
                for branch in branches_to_check:
                    branch_condition = next(
                        (condition for condition in Condition if condition.value == branch), None
                    )
                    consumer_active = (
                        stage.when == Condition.ALWAYS or stage.when == branch_condition
                    )
                    producer_active = source_stage is not None and (
                        source_stage.when == Condition.ALWAYS
                        or source_stage.when == branch_condition
                    )
                    if consumer_active and not producer_active:
                        issues.append(
                            ValidationIssue(
                                f"{path}.inputs",
                                f"conditional producer {source!r} is inactive in branch {branch!r}",
                            )
                        )
                        break
                _check_source_binding(f"{path}.inputs", reference, ancestors, stages, issues)

    for reference in workflow.required_outputs:
        parts = _reference_parts(reference)
        if parts is None:
            issues.append(
                ValidationIssue(f"{base}.required_outputs", f"invalid output binding {reference!r}")
            )
            continue
        source, _ = parts
        if source not in stage_ids or reference not in output_refs:
            issues.append(
                ValidationIssue(f"{base}.required_outputs", f"unknown output binding {reference!r}")
            )
        elif stages[source].when != Condition.ALWAYS:
            issues.append(
                ValidationIssue(
                    f"{base}.required_outputs",
                    f"required output {reference!r} is conditional and may be unavailable",
                )
            )

    parallel_groups: dict[str, int] = {}
    for stage in workflow.stages:
        if stage.kind == StageKind.WORKER and stage.parallel_group:
            assert stage.max_workers is not None
            parallel_groups[stage.parallel_group] = (
                parallel_groups.get(stage.parallel_group, 0) + stage.max_workers
            )
    for group, bound in parallel_groups.items():
        if bound > workflow.max_parallelism:
            issues.append(
                ValidationIssue(
                    f"{base}.parallel_groups.{group}",
                    "declared concurrent slot maxima exceed workflow cap",
                )
            )

    for index, redirect in enumerate(workflow.allowed_redirects):
        redirect_stage = stages.get(redirect.stage)
        path = f"{base}.allowed_redirects.{index}"
        if redirect_stage is None:
            issues.append(ValidationIssue(f"{path}.stage", "redirect target does not exist"))
            continue
        if (
            redirect_stage.kind != StageKind.WORKER
            or redirect_stage.slot_kind != SlotKind.SELECT_ONE
        ):
            issues.append(
                ValidationIssue(f"{path}.stage", "redirect requires a select_one worker stage")
            )
        if not set(redirect.allowed_profiles) <= set(redirect_stage.allowed_profiles):
            issues.append(
                ValidationIssue(
                    f"{path}.allowed_profiles", "redirect profiles exceed stage allowlist"
                )
            )
        if not set(redirect.allowed_profiles) <= allowed:
            issues.append(
                ValidationIssue(
                    f"{path}.allowed_profiles", "redirect profiles exceed workflow allowlist"
                )
            )
        if redirect_stage.default_profile in profiles:
            default_permissions = profiles[redirect_stage.default_profile].permissions
            for profile_id in redirect.allowed_profiles:
                profile = profiles.get(profile_id)
                if profile and not profile.permissions.is_within(default_permissions):
                    issues.append(
                        ValidationIssue(
                            f"{path}.allowed_profiles.{profile_id}",
                            "redirect would widen the selected profile permissions",
                        )
                    )
                if (
                    profile
                    and workflow.policy.permission_ceiling is not None
                    and not profile.permissions.is_within(workflow.policy.permission_ceiling)
                ):
                    issues.append(
                        ValidationIssue(
                            f"{base}.policy.permission_ceiling",
                            f"redirect profile {profile_id!r} exceeds the permission ceiling",
                        )
                    )

    if any(stage.when == Condition.REPAIR_NEEDED for stage in workflow.stages):
        if workflow.max_repair_cycles < 1:
            issues.append(
                ValidationIssue(
                    f"{base}.max_repair_cycles", "repair branch requires a positive budget"
                )
            )
        if not any(stage.kind == StageKind.REPAIR_GATE for stage in workflow.stages):
            issues.append(
                ValidationIssue(f"{base}.stages", "repair branches require a repair_gate")
            )

    _validate_required_paths(workflow, profiles, stages, ancestry, branches, issues)


def _validate_profile_policy(
    profile: AgentProfile,
    workflow: WorkflowPreset,
    backends: BackendSettings,
    issues: list[ValidationIssue],
) -> None:
    path = f"workflows.{workflow.id}.policy"
    if profile.backend not in workflow.policy.allowed_backends:
        issues.append(
            ValidationIssue(
                f"{path}.allowed_backends", f"profile {profile.id!r} uses {profile.backend!r}"
            )
        )
    if profile.model_binding not in workflow.policy.allowed_model_bindings:
        issues.append(
            ValidationIssue(
                f"{path}.allowed_model_bindings",
                f"profile {profile.id!r} uses {profile.model_binding!r}",
            )
        )
    if profile.backend not in backends.backends:
        issues.append(ValidationIssue(f"agents.{profile.id}.backend", "backend is not configured"))


def _check_source_binding(
    path: str,
    reference: str,
    ancestors: set[str],
    stages: dict[str, WorkflowStage],
    issues: list[ValidationIssue],
) -> None:
    parts = _reference_parts(reference)
    if parts is None:
        issues.append(ValidationIssue(path, f"invalid output binding {reference!r}"))
        return
    source, output = parts
    stage = stages.get(source)
    if stage is None or output not in stage.required_outputs:
        issues.append(ValidationIssue(path, f"missing output {reference!r}"))
        return
    if source not in ancestors:
        issues.append(
            ValidationIssue(path, f"output producer {source!r} is not an upstream dependency")
        )


def _validate_required_paths(
    workflow: WorkflowPreset,
    profiles: dict[str, AgentProfile],
    stages: dict[str, WorkflowStage],
    ancestry: dict[str, set[str]],
    branches: dict[str, dict[str, str]],
    issues: list[ValidationIssue],
) -> None:
    base = f"workflows.{workflow.id}.completion"

    def roles_for(stage: WorkflowStage) -> set[AgentRole]:
        return {
            profiles[profile_id].role
            for profile_id in stage.allowed_profiles
            if profile_id in profiles
        }

    def reaches_required(stage_id: str) -> bool:
        required_producers = {
            reference.partition(".")[0] for reference in workflow.required_outputs
        }
        return any(
            required_id == stage_id or stage_id in ancestry.get(required_id, set())
            for required_id in required_producers
        )

    def role_stage(
        reference: str, roles: set[AgentRole], branch: str, label: str
    ) -> WorkflowStage | None:
        parts = _reference_parts(reference)
        if parts is None:
            return None
        stage_id, output = parts
        stage = stages.get(stage_id)
        if stage is None or output not in stage.required_outputs:
            return None
        if not roles_for(stage) & roles:
            issues.append(
                ValidationIssue(
                    f"{base}.{branch}.{label}", "output producer has the wrong specialist role"
                )
            )
        if not reaches_required(stage_id):
            issues.append(
                ValidationIssue(
                    f"{base}.{branch}.{label}",
                    "verification output does not reach required completion",
                )
            )
        return stage

    if workflow.completion == WorkflowCompletion.REPORTS_PRESENT:
        for reference in workflow.required_outputs:
            parts = _reference_parts(reference)
            stage = stages.get(parts[0]) if parts else None
            if stage is None or stage.completion not in {
                StageCompletion.REPORT_PRESENT,
                StageCompletion.REPORT_PASSED,
                StageCompletion.ARTIFACT_READY,
            }:
                issues.append(
                    ValidationIssue(base, "required report output has no presence completion rule")
                )
    elif workflow.completion == WorkflowCompletion.VALIDATED_PROTOTYPE:
        matching = [
            stage
            for stage in workflow.stages
            if stage.kind == StageKind.WORKER
            and AgentRole.PROTOTYPE_VALIDATION in roles_for(stage)
            and stage.completion == StageCompletion.REPORT_PASSED
        ]
        if not matching:
            issues.append(
                ValidationIssue(base, "prototype completion requires a passing validation stage")
            )
        elif not any(reaches_required(stage.id) for stage in matching):
            issues.append(
                ValidationIssue(base, "prototype validation must reach a required output")
            )
    elif workflow.completion == WorkflowCompletion.VERIFIED_RESEARCH:
        matching = [
            stage
            for stage in workflow.stages
            if stage.kind == StageKind.WORKER
            and AgentRole.VERIFICATION in roles_for(stage)
            and stage.completion == StageCompletion.REPORT_PASSED
        ]
        if not matching:
            issues.append(
                ValidationIssue(base, "research completion requires a passing verification stage")
            )
        elif not any(reaches_required(stage.id) for stage in matching):
            issues.append(ValidationIssue(base, "verification must reach a required output"))
    elif workflow.completion == WorkflowCompletion.VERIFIED_REVISION:
        branch_items = list(branches.items()) or [("always", {})]
        for branch, bindings in branch_items:
            if bindings:
                review_ref = bindings.get("review")
                test_ref = bindings.get("test")
                if review_ref is None or test_ref is None:
                    issues.append(
                        ValidationIssue(
                            f"{base}.{branch}",
                            "verified revision branch must bind review and test reports",
                        )
                    )
                    continue
                review_stage = role_stage(review_ref, {AgentRole.REVIEW}, branch, "review")
                test_stage = role_stage(test_ref, {AgentRole.VALIDATION}, branch, "test")
                if review_stage and test_stage:
                    report_presence_gate = any(
                        gate.kind == StageKind.REPAIR_GATE
                        and gate.completion == StageCompletion.DECISION_RECORDED
                        and review_stage.id in gate.depends_on
                        and test_stage.id in gate.depends_on
                        for gate in workflow.stages
                    )
                    for label, stage in (("review", review_stage), ("test", test_stage)):
                        if stage.completion != StageCompletion.REPORT_PASSED and not (
                            branch == Condition.REPAIR_NOT_NEEDED.value and report_presence_gate
                        ):
                            issues.append(
                                ValidationIssue(
                                    f"{base}.{branch}.{label}",
                                    "required verification must pass or be consumed by the "
                                    "repair decision gate",
                                )
                            )
            else:
                for role, label in ((AgentRole.REVIEW, "review"), (AgentRole.VALIDATION, "test")):
                    matching = [
                        stage
                        for stage in workflow.stages
                        if stage.kind == StageKind.WORKER
                        and role in roles_for(stage)
                        and stage.completion == StageCompletion.REPORT_PASSED
                        and (branch == "always" or stage.when.value in {"always", branch})
                    ]
                    if not matching:
                        issues.append(
                            ValidationIssue(
                                f"{base}.{branch}.{label}",
                                "verified revision requires passing review and test stages",
                            )
                        )
                    elif not any(reaches_required(stage.id) for stage in matching):
                        issues.append(
                            ValidationIssue(
                                f"{base}.{branch}.{label}",
                                "verification stage must reach a required output",
                            )
                        )


def workflow_path(path: Path, workflow: WorkflowPreset) -> str:
    """Human-readable path helper used by config diagnostics."""
    return f"{path}: workflows.{workflow.id}"
