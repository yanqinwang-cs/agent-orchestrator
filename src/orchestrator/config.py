"""TOML loading and application-configuration validation entry points."""

from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ValidationError

from orchestrator.domain.models import (
    AgentCatalog,
    BackendSettings,
    DevelopmentConfig,
    ProfileOverlayFile,
    ProjectConfig,
    WorkflowOverlayFile,
    WorkflowPreset,
)
from orchestrator.validation import validate_application


@dataclass(frozen=True)
class ApplicationConfig:
    root: Path
    agents: AgentCatalog
    workflows: tuple[WorkflowPreset, ...]
    project: ProjectConfig
    backends: BackendSettings
    development: DevelopmentConfig


class ConfigLoadError(ValueError):
    """A TOML parse or typed-model error with a source path."""


def _model_error(path: Path, error: ValidationError) -> ConfigLoadError:
    lines: list[str] = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        lines.append(f"{path}: {location}: {item['msg']}")
    return ConfigLoadError("\n".join(lines))


def load_toml(path: Path) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigLoadError(f"{path}: {error}") from error
    try:
        value = tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ConfigLoadError(f"{path}: TOML parse error: {error}") from error
    return value


def parse_model[ModelT: BaseModel](model_type: type[ModelT], path: Path) -> ModelT:
    try:
        return model_type.model_validate(load_toml(path))
    except ValidationError as error:
        raise _model_error(path, error) from error


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_shipped_configuration(root: Path | None = None) -> ApplicationConfig:
    resolved_root = (root or repository_root()).resolve()
    agents = parse_model(AgentCatalog, resolved_root / "presets" / "agents.toml")
    workflows = tuple(
        parse_model(WorkflowPreset, path)
        for path in sorted((resolved_root / "presets" / "workflows").glob("*.toml"))
    )
    project = parse_model(ProjectConfig, resolved_root / "config" / "project.example.toml")
    backends = parse_model(BackendSettings, resolved_root / "config" / "backends.toml")
    development = parse_model(DevelopmentConfig, resolved_root / "config" / "development.toml")
    if len(workflows) != 6:
        raise ConfigLoadError(
            f"{resolved_root / 'presets' / 'workflows'}: expected six shipped workflows, "
            f"found {len(workflows)}"
        )
    validate_application(agents, workflows, backends, project)
    return ApplicationConfig(resolved_root, agents, workflows, project, backends, development)


def validate_config_file(path: Path, root: Path | None = None) -> str:
    """Validate a typed TOML file plus its application-level references."""
    source = path.expanduser().resolve()
    app = load_shipped_configuration(root)
    raw = load_toml(source)

    if "agents" in raw:
        candidate_agents = parse_model(AgentCatalog, source)
        validate_application(candidate_agents, app.workflows, app.backends, app.project)
        return f"agent catalog {len(candidate_agents.agents)} profiles"
    if "stages" in raw:
        candidate_workflow = parse_model(WorkflowPreset, source)
        workflows = tuple(item for item in app.workflows if item.id != candidate_workflow.id) + (
            candidate_workflow,
        )
        validate_application(app.agents, workflows, app.backends, app.project)
        return f"workflow {candidate_workflow.id}"
    if "backends" in raw:
        candidate_backends = parse_model(BackendSettings, source)
        validate_application(app.agents, app.workflows, candidate_backends, app.project)
        return f"backend settings ({len(candidate_backends.backends)} backends)"
    if "allowed_workflows" in raw:
        candidate_project = parse_model(ProjectConfig, source)
        validate_application(app.agents, app.workflows, app.backends, candidate_project)
        return f"project {candidate_project.id}"
    if "presets" in raw:
        candidate_development = parse_model(DevelopmentConfig, source)
        return f"development presets ({len(candidate_development.presets)})"
    if "profiles" in raw:
        candidate_profile_overlays = parse_model(ProfileOverlayFile, source)
        for index, profile_overlay in enumerate(candidate_profile_overlays.profiles):
            profile = next(
                (item for item in app.agents.agents if item.id == profile_overlay.profile_id), None
            )
            if profile is None:
                raise ConfigLoadError(
                    f"{source}: profiles.{index}.profile_id: "
                    f"unknown profile {profile_overlay.profile_id!r}"
                )
            if (
                profile_overlay.permissions is not None
                and not profile_overlay.permissions.is_within(profile.permissions)
            ):
                raise ConfigLoadError(
                    f"{source}: profiles.{index}.permissions: permission widening is forbidden"
                )
        return f"profile overlays ({len(candidate_profile_overlays.profiles)})"
    if "workflows" in raw:
        candidate_workflow_overlays = parse_model(WorkflowOverlayFile, source)
        workflow_by_id = {workflow.id: workflow for workflow in app.workflows}
        for overlay_index, workflow_overlay in enumerate(candidate_workflow_overlays.workflows):
            workflow = workflow_by_id.get(workflow_overlay.workflow_id)
            if workflow is None:
                raise ConfigLoadError(
                    f"{source}: workflows.{overlay_index}.workflow_id: unknown workflow "
                    f"{workflow_overlay.workflow_id!r}"
                )
            stages = {stage.id: stage for stage in workflow.stages}
            for stage_id, count in workflow_overlay.worker_counts.items():
                stage = stages.get(stage_id)
                if (
                    stage is None
                    or stage.min_workers is None
                    or stage.max_workers is None
                    or stage.slot_kind is None
                ):
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.worker_counts.{stage_id}: "
                        "unknown worker stage"
                    )
                if not stage.min_workers <= count <= stage.max_workers:
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.worker_counts.{stage_id}: "
                        "outside declared bounds"
                    )
                if count != stage.min_workers and not workflow.policy.allow_count_selection:
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.worker_counts.{stage_id}: "
                        "count selection is forbidden by policy"
                    )
                if count != stage.min_workers and stage.slot_kind.value != "elastic":
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.worker_counts.{stage_id}: "
                        "only elastic slots may change count"
                    )
            for stage_id, profile_id in workflow_overlay.default_profiles.items():
                stage = stages.get(stage_id)
                if stage is None or profile_id not in stage.allowed_profiles:
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.default_profiles.{stage_id}: "
                        "profile is outside stage allowlist"
                    )
                if len(stage.allowed_profiles) > 1 and not workflow.policy.allow_profile_selection:
                    raise ConfigLoadError(
                        f"{source}: workflows.{overlay_index}.default_profiles.{stage_id}: "
                        "profile selection is forbidden by policy"
                    )
        return f"workflow overlays ({len(candidate_workflow_overlays.workflows)})"
    raise ConfigLoadError(
        f"{source}: cannot identify an application configuration; "
        "expected agents, stages, backends, "
        "allowed_workflows, or presets"
    )


def export_model_schema(model_type: type[BaseModel], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema = model_type.model_json_schema()
    path.write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
