"""Provider-independent catalog and composition contracts."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FiniteFloat,
    StringConstraints,
    field_validator,
    model_validator,
)

ResourceId = Annotated[
    str,
    StringConstraints(
        min_length=3,
        max_length=120,
        pattern=r"^[a-z0-9][a-z0-9._/-]*$",
    ),
]
Version = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9.+_-]*$",
    ),
]


class ResourceKind(StrEnum):
    SKILL = "skill"
    PROMPT = "prompt"
    PLUGIN = "plugin"
    TOOL = "tool"
    MCP_SERVER = "mcp_server"
    AGENT_CONFIG = "agent_config"


RESOURCE_LABELS: dict[ResourceKind, str] = {
    ResourceKind.SKILL: "Skills",
    ResourceKind.PROMPT: "Prompts",
    ResourceKind.PLUGIN: "Plugins",
    ResourceKind.TOOL: "Tools",
    ResourceKind.MCP_SERVER: "MCP servers",
    ResourceKind.AGENT_CONFIG: "Agent configurations",
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ResourceDefinition(Contract):
    id: ResourceId
    kind: ResourceKind
    name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)


class ResourceVersion(Contract):
    resource_id: ResourceId
    version: Version
    body: str = Field(min_length=1, max_length=40_000)
    metadata: dict[str, str] = Field(default_factory=dict)
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class CatalogResource(Contract):
    definition: ResourceDefinition
    versions: tuple[ResourceVersion, ...]


class CompositionBinding(Contract):
    target: str = Field(min_length=1, max_length=80)
    ordinal: int = Field(ge=0)
    resource_id: ResourceId
    version: Version
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    name: str = Field(min_length=1, max_length=120)
    kind: ResourceKind


ModelParameter = str | int | FiniteFloat | bool | None


class ModelSettings(Contract):
    slot: str = Field(min_length=1, max_length=80)
    provider: str = Field(min_length=1, max_length=120)
    model: str = Field(min_length=1, max_length=160)
    parameters: dict[str, ModelParameter] = Field(default_factory=dict)

    @field_validator("parameters")
    @classmethod
    def reject_secret_fields(
        cls, parameters: dict[str, ModelParameter]
    ) -> dict[str, ModelParameter]:
        sensitive_name = re.compile(
            r"(api[_-]?key|secret|password|credential|authorization|access[_-]?token|"
            r"auth[_-]?token|private[_-]?key|(^|[_-])token($|[_-]))",
            re.IGNORECASE,
        )
        safe_token_limits = {"max_tokens", "max_output_tokens", "context_tokens", "token_budget"}
        forbidden = [
            name
            for name in parameters
            if sensitive_name.search(name) and name.casefold() not in safe_token_limits
        ]
        if forbidden:
            raise ValueError(
                "Model settings cannot contain credentials or secret fields: "
                + ", ".join(sorted(forbidden))
            )
        return parameters


class CompositionDraft(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    instructions: str = Field(default="", max_length=20_000)
    bindings: tuple[CompositionBinding, ...] = Field(min_length=1, max_length=40)
    model_settings: tuple[ModelSettings, ...] = Field(default=(), max_length=20)

    @model_validator(mode="after")
    def unique_bindings_and_model_slots(self) -> CompositionDraft:
        binding_positions = [(binding.target, binding.ordinal) for binding in self.bindings]
        if len(binding_positions) != len(set(binding_positions)):
            raise ValueError("Binding ordinals must be unique within each target.")
        slots = [settings.slot for settings in self.model_settings]
        if len(slots) != len(set(slots)):
            raise ValueError("Model settings slots must be unique within a composition.")
        return self


class CompositionRevision(Contract):
    composition_id: str
    revision: int = Field(ge=1)
    schema_version: int = Field(ge=1)
    name: str
    description: str
    instructions: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: str
    bindings: tuple[CompositionBinding, ...]
    model_settings: tuple[ModelSettings, ...]


class SavedComposition(Contract):
    id: str
    current_revision: int = Field(ge=1)
    created_at: str
    updated_at: str
    revision: CompositionRevision
    history: tuple[CompositionRevision, ...]


class MissingBindingError(ValueError):
    """A submitted resource/version pair does not exist in the catalog."""


class CompositionNotFoundError(LookupError):
    """The requested saved composition does not exist."""


class StaleCompositionError(RuntimeError):
    """Another save advanced the composition after the edit form was loaded."""
