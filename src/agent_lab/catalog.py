"""Small built-in discovery catalog; these definitions are not executable integrations."""

from dataclasses import dataclass

from agent_lab.domain import ResourceDefinition, ResourceKind


@dataclass(frozen=True)
class SeedVersion:
    version: str
    body: str
    metadata: dict[str, str]


@dataclass(frozen=True)
class SeedResource:
    definition: ResourceDefinition
    versions: tuple[SeedVersion, ...]


BUILTIN_CATALOG: tuple[SeedResource, ...] = (
    SeedResource(
        definition=ResourceDefinition(
            id="skill/review-checklist",
            kind=ResourceKind.SKILL,
            name="Review checklist",
            summary="A compact checklist for inspecting a proposed code change.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Inspect behavior, boundary conditions, security, and test coverage. "
                    "Report actionable findings with file and line references."
                ),
                metadata={"maintainer": "Agent Lab", "format": "plain-text"},
            ),
            SeedVersion(
                version="1.1.0",
                body=(
                    "Review the change against its stated intent. Check behavior, edge cases, "
                    "security, and tests. Prioritize actionable findings with file and line "
                    "references; distinguish confirmed defects from questions."
                ),
                metadata={"maintainer": "Agent Lab", "format": "plain-text"},
            ),
        ),
    ),
    SeedResource(
        definition=ResourceDefinition(
            id="prompt/clarify-task",
            kind=ResourceKind.PROMPT,
            name="Clarify a task",
            summary="A prompt structure for making objectives and acceptance criteria explicit.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Restate the requested outcome. Identify constraints and observable "
                    "acceptance criteria. Ask only for information that blocks safe progress."
                ),
                metadata={"maintainer": "Agent Lab", "format": "plain-text"},
            ),
        ),
    ),
    SeedResource(
        definition=ResourceDefinition(
            id="plugin/interface-notes",
            kind=ResourceKind.PLUGIN,
            name="Interface notes plugin definition",
            summary="A descriptive bundle for preserving interface decisions in project notes.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Purpose: capture a concise record of interface decisions and constraints.\n"
                    "Inputs: decision, rationale, and affected contract.\n"
                    "Effects: none. This catalog entry describes a plugin; it does not install one."
                ),
                metadata={"maintainer": "Agent Lab", "format": "descriptive-contract"},
            ),
        ),
    ),
    SeedResource(
        definition=ResourceDefinition(
            id="tool/workspace-search",
            kind=ResourceKind.TOOL,
            name="Workspace search tool definition",
            summary="A descriptive tool contract for searching files in a workspace.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Purpose: find text or paths in a user-selected workspace.\n"
                    "Inputs: query (required string), optional path_glob (string).\n"
                    "Output: matching paths and line excerpts.\n"
                    "Effects: read-only. This catalog record does not install or run a tool."
                ),
                metadata={"maintainer": "Agent Lab", "interface": "descriptive-contract"},
            ),
        ),
    ),
    SeedResource(
        definition=ResourceDefinition(
            id="mcp/filesystem-readonly",
            kind=ResourceKind.MCP_SERVER,
            name="Read-only filesystem MCP profile",
            summary="An example MCP server profile with read-only access intent.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Transport: stdio (illustrative).\n"
                    "Permission intent: read-only access to an explicitly selected directory.\n"
                    "This profile is descriptive only. No server is launched by this website."
                ),
                metadata={"maintainer": "Agent Lab", "profile": "example-only"},
            ),
        ),
    ),
    SeedResource(
        definition=ResourceDefinition(
            id="agent/research-assistant",
            kind=ResourceKind.AGENT_CONFIG,
            name="Research assistant configuration",
            summary="A provider-neutral starting configuration for evidence-led research.",
        ),
        versions=(
            SeedVersion(
                version="1.0.0",
                body=(
                    "Role: research assistant.\n"
                    "Method: separate sourced facts from interpretation and uncertainty.\n"
                    "Output: concise findings with source references and unresolved questions.\n"
                    "This is configuration data, not a runnable agent."
                ),
                metadata={"maintainer": "Agent Lab", "format": "plain-text"},
            ),
        ),
    ),
)
