from pathlib import Path

import pytest
from pydantic import ValidationError

from orchestrator.config import parse_model
from orchestrator.domain.models import (
    Effort,
    ModelBindingSettings,
    ProfileOverlay,
    ProfileOverlayFile,
    ResolvedOrchestratorPolicy,
    RunOverrides,
    WorkflowOverlay,
)
from orchestrator.resolution import ResolutionError, resolve_run


def _project_with_models(app_config, efforts: list[str] | None = None):
    binding = ModelBindingSettings(
        backend="codex",
        model_id="offline-test-model",
        allowed_efforts=efforts or ["high", "medium"],
    )
    return app_config.project.model_copy(update={"models": {"standard": binding}})


def _availability(efforts: set[Effort] | None = None):
    return {"codex": {"offline-test-model": efforts or {Effort.HIGH, Effort.MEDIUM}}}


def _review(app_config):
    return next(workflow for workflow in app_config.workflows if workflow.id == "review")


def _resolve(app_config, **kwargs):
    return resolve_run(
        "Review the current changes",
        _project_with_models(app_config),
        _review(app_config),
        app_config.agents.agents,
        model_availability=_availability(),
        **kwargs,
    )


def test_resolved_spec_is_immutable_and_hash_is_canonical(app_config) -> None:
    first = _resolve(app_config)
    second = _resolve(app_config)
    changed = resolve_run(
        "Review different changes",
        _project_with_models(app_config),
        _review(app_config),
        app_config.agents.agents,
        model_availability=_availability(),
    )

    assert first.snapshot_hash == second.snapshot_hash
    assert len(first.snapshot_hash) == 64
    assert first.snapshot_hash != changed.snapshot_hash
    with pytest.raises(ValidationError):
        first.task = "mutated"
    with pytest.raises(ValidationError):
        first.workflow.stages[0].id = "mutated"
    assert isinstance(first.workflow.stages, tuple)


def test_project_context_tightens_profile_context(app_config) -> None:
    project = _project_with_models(app_config).model_copy(
        update={"context": app_config.project.context.model_copy(update={"max_bytes": 2048})}
    )
    spec = resolve_run(
        "Review the current changes",
        project,
        _review(app_config),
        app_config.agents.agents,
        model_availability=_availability(),
    )
    assert spec.profiles[0].context_policy.max_bytes == 2048
    assert spec.profiles[0].context_policy.include_full_history is False


def test_profile_and_workflow_overlays_are_applied_to_resolved_snapshot(app_config) -> None:
    feature = next(workflow for workflow in app_config.workflows if workflow.id == "feature")
    spec = resolve_run(
        "Implement a small feature",
        _project_with_models(app_config),
        feature,
        app_config.agents.agents,
        model_availability=_availability(),
        profile_overlays=(
            ProfileOverlay(profile_id="planner", base_prompt="Use the supplied plan only."),
        ),
        workflow_overlays=(
            WorkflowOverlay(
                workflow_id="feature",
                worker_counts={"implement": 2},
                default_profiles={"implement": "implementer"},
            ),
        ),
    )
    implementation = next(stage for stage in spec.workflow.stages if stage.id == "implement")
    selection = next(item for item in spec.selections if item.stage_id == "implement")
    planner = next(profile for profile in spec.profiles if profile.id == "planner")
    assert implementation.default_profile == "implementer"
    assert selection.worker_count == 2
    assert selection.profile_ids == ("implementer", "implementer")
    assert planner.base_prompt == "Use the supplied plan only."


def test_missing_project_model_binding_is_rejected(app_config) -> None:
    with pytest.raises(
        ResolutionError, match=r"project.models.standard: required model binding.*missing"
    ):
        resolve_run(
            "Review the current changes",
            app_config.project,
            _review(app_config),
            app_config.agents.agents,
            model_availability=_availability(),
        )


def test_backend_unsupported_effort_is_rejected(app_config, repo_root: Path) -> None:
    path = repo_root / "tests" / "fixtures" / "invalid" / "unsupported-effort.toml"
    overlays = parse_model(ProfileOverlayFile, path).profiles
    project = _project_with_models(app_config, ["high", "ultra"])
    with pytest.raises(ResolutionError, match="unsupported effort 'ultra'"):
        resolve_run(
            "Review the current changes",
            project,
            _review(app_config),
            app_config.agents.agents,
            model_availability=_availability({Effort.HIGH}),
            profile_overlays=overlays,
        )


def test_permission_widening_is_rejected_by_resolver(app_config, repo_root: Path) -> None:
    path = repo_root / "tests" / "fixtures" / "invalid" / "permission-widening.toml"
    overlays = parse_model(ProfileOverlayFile, path).profiles
    with pytest.raises(ResolutionError, match="permission widening is forbidden"):
        _resolve(app_config, profile_overlays=overlays)


def test_worker_count_override_must_stay_within_bounds(app_config) -> None:
    feature = next(workflow for workflow in app_config.workflows if workflow.id == "feature")
    profiles = app_config.agents.agents
    project = _project_with_models(app_config)
    overrides = RunOverrides(worker_counts={"implement": 4})
    with pytest.raises(
        ResolutionError, match=r"overrides.worker_counts.implement: 4 is outside \[1, 3\]"
    ):
        resolve_run(
            "Implement a small feature",
            project,
            feature,
            profiles,
            model_availability=_availability(),
            overrides=overrides,
        )


def test_worker_count_must_fit_project_concurrency(app_config) -> None:
    feature = next(workflow for workflow in app_config.workflows if workflow.id == "feature")
    project = _project_with_models(app_config).model_copy(update={"max_parallelism": 2})
    with pytest.raises(ResolutionError, match="exceeds effective concurrency cap 2"):
        resolve_run(
            "Implement a small feature",
            project,
            feature,
            app_config.agents.agents,
            model_availability=_availability(),
            overrides=RunOverrides(worker_counts={"implement": 3}),
        )


def test_profile_selection_is_limited_to_declared_recipients(app_config) -> None:
    prototype = next(workflow for workflow in app_config.workflows if workflow.id == "prototype")
    project = _project_with_models(app_config)
    with pytest.raises(ResolutionError, match="outside the stage allowlist"):
        resolve_run(
            "Build the prototype",
            project,
            prototype,
            app_config.agents.agents,
            model_availability=_availability(),
            overrides=RunOverrides(profile_selections={"implement": "reviewer"}),
        )


def test_resolved_run_preserves_explicit_semantic_decision_configuration(app_config) -> None:
    prototype = next(workflow for workflow in app_config.workflows if workflow.id == "prototype")
    assert prototype.policy.decision_questions

    spec = resolve_run(
        "Choose an approved implementation specialist",
        _project_with_models(app_config),
        prototype,
        app_config.agents.agents,
        model_availability=_availability(),
    )

    question = spec.workflow.policy.decision_questions[0]
    redirect = next(item for item in spec.workflow.allowed_redirects if item.stage == "implement")
    assert question.question_id == "implementer_choice"
    assert question.inference_binding.mechanism.value == "deterministic_policy"
    assert tuple(item.source_ref for item in question.evidence_requirements) == (
        "run.task",
        "plan.plan",
    )
    assert redirect.allowed_profiles == ("prototype-implementer", "implementer")


def test_pre_m5_resolved_policy_payload_remains_readable(app_config) -> None:
    spec = _resolve(app_config)
    legacy_payload = spec.workflow.policy.model_dump(mode="json")
    legacy_payload.pop("decision_questions")

    restored = ResolvedOrchestratorPolicy.model_validate(legacy_payload)

    assert restored == spec.workflow.policy.model_copy(update={"decision_questions": ()})
