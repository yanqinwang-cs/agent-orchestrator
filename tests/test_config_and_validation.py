import re
from pathlib import Path

import pytest

from orchestrator.config import ConfigLoadError, load_shipped_configuration, validate_config_file
from orchestrator.domain.decisions import DecisionEvidenceRequirement
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


@pytest.mark.parametrize("source,output", [("implement", "changes"), ("validate", "report")])
def test_decision_evidence_cannot_depend_on_its_target_or_downstream(app_config, source, output):
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0].model_copy(
        update={
            "evidence_requirements": (
                DecisionEvidenceRequirement(
                    kind="stage_output",
                    stage_id=source,
                    output_name=output,
                    inclusion_reason="Evidence must exist before choosing the recipient.",
                ),
            ),
        }
    )
    workflow = prototype.model_copy(
        update={
            "policy": prototype.policy.model_copy(update={"decision_questions": [question]}),
        }
    )
    with pytest.raises(ConfigValidationError, match="not an ancestor of the decision stage"):
        validate_application(app_config.agents, [workflow], app_config.backends)


def test_decision_evidence_validation_is_independent_of_stage_declaration_order(app_config):
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    reordered = prototype.model_copy(update={"stages": list(reversed(prototype.stages))})
    validate_application(app_config.agents, [reordered], app_config.backends)


def test_multiple_decisions_for_one_redirect_are_rejected(app_config):
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    question = prototype.policy.decision_questions[0]
    workflow = prototype.model_copy(
        update={
            "policy": prototype.policy.model_copy(
                update={
                    "decision_questions": [
                        question,
                        question.model_copy(update={"question_id": "another_choice"}),
                    ],
                }
            )
        }
    )
    with pytest.raises(ConfigValidationError, match="one redirect decision per stage"):
        validate_application(app_config.agents, [workflow], app_config.backends)


def test_missing_input_output_binding_is_rejected(app_config) -> None:
    review = next(workflow for workflow in app_config.workflows if workflow.id == "review")
    bad_stage = review.stages[0].model_copy(update={"inputs": ["task", "missing.report"]})
    bad_workflow = review.model_copy(update={"stages": [bad_stage]})

    with pytest.raises(ConfigValidationError, match=re.escape("missing output 'missing.report'")):
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


def _validate_feature(app_config, workflow):
    validate_application(
        app_config.agents,
        [workflow],
        app_config.backends,
        app_config.project.model_copy(update={"allowed_workflows": [workflow.id]}),
    )


def test_conditional_optional_stage_requires_allow_optional_skip(app_config) -> None:
    feature = next(item for item in app_config.workflows if item.id == "feature")
    policy = feature.policy.model_copy(update={"allow_optional_skip": False})

    with pytest.raises(ConfigValidationError, match=r"stages.repair.optional"):
        _validate_feature(app_config, feature.model_copy(update={"policy": policy}))


def test_verified_revision_requires_the_stage_names_the_engine_reads(app_config) -> None:
    feature = next(item for item in app_config.workflows if item.id == "feature")
    renamed = [
        stage.model_copy(
            update={
                "id": "decide" if stage.id == "repair_gate" else stage.id,
                "depends_on": [
                    "decide" if item == "repair_gate" else item for item in stage.depends_on
                ],
            }
        )
        for stage in feature.stages
    ]

    with pytest.raises(ConfigValidationError, match="stage must be named 'repair_gate'"):
        _validate_feature(app_config, feature.model_copy(update={"stages": renamed}))


def test_repair_gate_name_is_enforced_in_any_workflow_that_has_one(app_config) -> None:
    feature = next(item for item in app_config.workflows if item.id == "feature")
    renamed = [
        stage.model_copy(
            update={
                "id": "decide" if stage.id == "repair_gate" else stage.id,
                "depends_on": [
                    "decide" if item == "repair_gate" else item for item in stage.depends_on
                ],
            }
        )
        for stage in feature.stages
    ]
    workflow = feature.model_copy(
        update={"stages": renamed, "completion": WorkflowCompletion.REPORTS_PRESENT}
    )

    with pytest.raises(ConfigValidationError, match="stage must be named 'repair_gate'"):
        _validate_feature(app_config, workflow)


def test_repair_branch_must_declare_a_revision_output(app_config) -> None:
    feature = next(item for item in app_config.workflows if item.id == "feature")
    branches = {name: dict(outputs) for name, outputs in feature.branch_outputs.items()}
    del branches["repair_needed"]["revision"]

    with pytest.raises(ConfigValidationError, match="must declare a revision output"):
        _validate_feature(app_config, feature.model_copy(update={"branch_outputs": branches}))


def test_verified_research_requires_a_stage_named_verify(app_config) -> None:
    research = next(item for item in app_config.workflows if item.id == "research")
    renamed = [
        stage.model_copy(
            update={
                "id": "check" if stage.id == "verify" else stage.id,
                "depends_on": ["check" if item == "verify" else item for item in stage.depends_on],
            }
        )
        for stage in research.stages
    ]
    required = [item.replace("verify.", "check.") for item in research.required_outputs]

    with pytest.raises(ConfigValidationError, match="stage must be named 'verify'"):
        _validate_feature(
            app_config,
            research.model_copy(update={"stages": renamed, "required_outputs": required}),
        )


def test_duplicate_profile_in_a_redirect_is_rejected(app_config) -> None:
    prototype = next(item for item in app_config.workflows if item.id == "prototype")
    redirects = [
        item.model_copy(
            update={"allowed_profiles": [*item.allowed_profiles, item.allowed_profiles[0]]}
        )
        for item in prototype.allowed_redirects
    ]

    with pytest.raises(ConfigValidationError, match="duplicate profile"):
        _validate_feature(app_config, prototype.model_copy(update={"allowed_redirects": redirects}))


def test_overlay_path_settings_are_rejected_until_loading_exists(app_config) -> None:
    project = app_config.project.model_copy(update={"agent_overlay_paths": ["overlays/a.toml"]})
    with pytest.raises(ConfigValidationError, match=re.escape("project.agent_overlay_paths")):
        validate_application(app_config.agents, app_config.workflows, app_config.backends, project)

    project = app_config.project.model_copy(update={"workflow_overlay_paths": ["w.toml"]})
    with pytest.raises(ConfigValidationError, match=re.escape("project.workflow_overlay_paths")):
        validate_application(app_config.agents, app_config.workflows, app_config.backends, project)

    profile = app_config.agents.agents[0].model_copy(update={"overlay_paths": ["x.toml"]})
    catalog = app_config.agents.model_copy(
        update={"agents": [profile, *app_config.agents.agents[1:]]}
    )
    with pytest.raises(ConfigValidationError, match=r"agents\..*overlay_paths"):
        validate_application(catalog, app_config.workflows, app_config.backends, app_config.project)
