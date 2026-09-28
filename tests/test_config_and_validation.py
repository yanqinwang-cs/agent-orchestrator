from pathlib import Path

import pytest

from orchestrator.config import ConfigLoadError, load_shipped_configuration, validate_config_file
from orchestrator.domain.models import PermissionSet, SandboxMode, WorkflowCompletion
from orchestrator.validation import ConfigValidationError, validate_application


def test_all_shipped_application_configs_validate(app_config) -> None:
    assert len(app_config.agents.agents) == 11
    assert len(app_config.workflows) == 6
    assert len(app_config.development.presets) == 6
    assert app_config.project.models == {}
    assert "fake" in app_config.backends.backends


def test_development_presets_are_not_loaded_as_product_profiles(repo_root: Path) -> None:
    app = load_shipped_configuration(repo_root)
    assert {profile.id for profile in app.agents.agents}.isdisjoint(app.development.presets)


def test_unknown_profile_is_reported_with_workflow_field_path(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_stage = review.stages[0].model_copy(update={"allowed_profiles": ["missing-agent"]})
    bad_workflow = review.model_copy(update={"stages": [bad_stage]})

    with pytest.raises(
        ConfigValidationError, match=r"workflows.review.stages.review.allowed_profiles"
    ):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["review"]}),
        )


def test_dependency_cycle_is_rejected(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_stage = review.stages[0].model_copy(update={"depends_on": ["review"]})
    bad_workflow = review.model_copy(update={"stages": [bad_stage]})

    with pytest.raises(
        ConfigValidationError, match=r"workflows.review.stages.review.depends_on: dependency cycle"
    ):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["review"]}),
        )


def test_missing_input_output_binding_is_rejected(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_stage = review.stages[0].model_copy(update={"inputs": ["task", "missing.report"]})
    bad_workflow = review.model_copy(update={"stages": [bad_stage]})

    with pytest.raises(ConfigValidationError, match="missing output 'missing.report'"):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["review"]}),
        )


def test_policy_permission_expansion_is_rejected(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_policy = review.policy.model_copy(update={"allow_permission_expansion": True})
    bad_workflow = review.model_copy(update={"policy": bad_policy})

    with pytest.raises(ConfigValidationError, match="v1 does not permit permission expansion"):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["review"]}),
        )


def test_permission_ceiling_cannot_be_lower_than_required_profile(app_config) -> None:
    prototype = next(workflow for workflow in app_config.workflows if workflow.id == "prototype")
    policy = prototype.policy.model_copy(
        update={"permission_ceiling": PermissionSet(sandbox=SandboxMode.READ_ONLY)}
    )
    bad_workflow = prototype.model_copy(update={"policy": policy})
    with pytest.raises(ConfigValidationError, match="permission ceiling is lower than profile"):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["prototype"]}),
        )


def test_verified_revision_requires_review_and_test_paths(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_workflow = review.model_copy(update={"completion": WorkflowCompletion.VERIFIED_REVISION})
    with pytest.raises(
        ConfigValidationError, match="verified revision requires passing review and test stages"
    ):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project.model_copy(update={"allowed_workflows": ["review"]}),
        )


def test_feature_repair_branch_requires_fresh_passing_reports(app_config) -> None:
    feature = next(workflow for workflow in app_config.workflows if workflow.id == "feature")
    branches = {branch: dict(outputs) for branch, outputs in feature.branch_outputs.items()}
    branches["repair_needed"]["review"] = "review.report"
    bad_workflow = feature.model_copy(update={"branch_outputs": branches})
    with pytest.raises(
        ConfigValidationError,
        match="required verification must pass or be consumed by the repair decision gate",
    ):
        validate_application(
            app_config.agents,
            [bad_workflow],
            app_config.backends,
            app_config.project,
        )


@pytest.mark.parametrize(
    ("fixture", "message"),
    [
        ("permission-widening.toml", "permission widening is forbidden"),
        ("out-of-bounds-slot.toml", "outside declared bounds"),
        ("unknown-overlay-profile.toml", "profile is outside stage allowlist"),
    ],
)
def test_invalid_overlay_fixtures_fail_with_field_paths(
    repo_root: Path, fixture: str, message: str
) -> None:
    path = repo_root / "tests" / "fixtures" / "invalid" / fixture
    with pytest.raises(ConfigLoadError, match=message):
        validate_config_file(path, repo_root)


def test_application_config_schema_rejects_unknown_fields(tmp_path: Path) -> None:
    path = tmp_path / "backend.toml"
    path.write_text("schema_version=1\nunknown=true\n[backends]\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError, match="Extra inputs are not permitted"):
        validate_config_file(path)
