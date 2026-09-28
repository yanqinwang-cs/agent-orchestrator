# Agent Orchestrator

Build the local orchestration app described in `docs/IMPLEMENTATION_PLAN.md`. Development execution presets in `config/development.toml` are separate from product AgentProfiles in `presets/agents.toml`.

Before editing, read the requested milestone and affected contracts. For runtime, persistence, intervention or backend changes, also read `docs/INTEGRATION_AUDIT.md`. Keep work bounded to the requested milestone.

- Domain models depend on Python and Pydantic, never FastAPI or Codex types. Backend adapters translate provider details at their boundary.
- Preserve the immutable resolved attempt specification. Record steering, retries, status changes and handoffs as attributable events. A retry creates a new attempt.
- Commit state changes, events, reservations and dispatch intent together. External launch acknowledgement is a separate transaction; uncertain launches require reconciliation.
- Preserve required verification, declared topology, permission ceilings and concurrency limits. Propose consequential contract or product changes explicitly before implementing them.
- Classify failures before retrying. Enforce attempt and time budgets; retain failed evidence.
- Test state transitions and integration boundaries with deterministic fake workers. Live Codex tests are explicit opt-in and are never a default test dependency.
- Version persisted schemas and presets. Prefer additive compatibility; provide a migration and fixture for breaking changes.
- Update the architecture document and relevant fixtures when changing a core contract. Report implemented behavior, validation and remaining limitations separately.
- Preserve unrelated files and source-project worktrees. Use isolated workspaces for product workers that write files.
- Keep the app a single local service with SQLite and filesystem artifacts. New infrastructure needs a demonstrated requirement.

First task: `tasks/01-foundation.md`. Development commands become available in milestone 1; `README.md` lists their intended interface.
