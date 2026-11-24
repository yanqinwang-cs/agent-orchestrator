# Agent Lab

This `AGENTS.md` file is the **project-level instruction and continuity document** for this repository.

Treat it as the authoritative source for the project's stable intent, operating principles, and scope unless the user explicitly overrides it. Do not assume that a separate project-continuity or memory file exists.

The repository is being repurposed from the old Agent Orchestrator into the public experimentation and benchmarking harness for the Agent Lab venture/research project.

Git history is the archive for obsolete work. Active files should reflect the current project only.

## Current work and authority boundaries

The current task is to build the testing website: a benchmarking platform for the harness that includes skills, plugins, MCPs, and related integrations.
Clarify the website's users, experiment flows, and evaluation requirements before fixing its implementation scope.
Website work does not authorize building, completing, or modifying the harness.
Do not consult, mention, or follow the previous milestone document unless the user explicitly asks to revisit it or explicitly authorizes continuing harness work.

The current product hypothesis is a translator that intelligently chooses representation formats for information transfer between agents, tool interfaces, and other intelligent-system boundaries.
This hypothesis is context only; do not begin its design or implementation without explicit user authorization.

## Project purpose

This repository supports a venture/research project around **intelligent-system interfaces and experimentation**.

The long-term goal is not to prescribe one universal agent architecture, model provider, orchestration framework, workflow topology, communication format, or user experience.

The project should remain a flexible, inspectable substrate for defining and evaluating intelligent systems and the interfaces between their components.

A central research question is how intelligent components should represent and transfer information.

Relevant boundaries may include:

- agent ↔ agent
- agent ↔ tool
- agent ↔ skill
- agent ↔ memory/artifact
- agent ↔ runtime
- model ↔ model
- later, embodied-system boundaries such as perception ↔ planner ↔ controller

Do not assume natural language, JSON, or any other single representation is universally best.

Different interfaces may need different trade-offs in latency, fidelity, information density, bandwidth, compute/cost, uncertainty preservation, auditability, durability, interoperability, and authority/safety.

Guiding principle:

> Use the cheapest representation that preserves the information required for the downstream decision.

Do not reduce the project to prompt compression. Prompt compression is only one nearby technique.

## Platform role

The repository may support both:

1. an experimental harness for controlled evaluation; and
2. a public-facing benchmark/discovery surface.

These should share the same underlying experiment and result model where practical.

The platform may compare agents, skills, tools, harnesses, workflows, and information-interface strategies.

Do not assume in advance which of these becomes the eventual commercial product.

## Preferred execution policy

Use mature external infrastructure where it saves engineering effort.

Current preferred direction:

- **Deep Agents** as the initial agent harness;
- **LangChain/LangGraph primitives** where Deep Agents depends on or exposes them;
- **Amazon Bedrock AgentCore Runtime** as the preferred hosted execution environment;
- model/provider bindings kept replaceable and experiment definitions kept provider-agnostic.

Do not make Deep Agents, LangChain, LangGraph, AWS, Bedrock, or AgentCore types part of generic persisted domain contracts when an adapter boundary is sufficient.

The existing Agent Orchestrator code is prior work, an optional backend, and a source of tested execution ideas. It is **not** mandatory infrastructure for new work.

Custom orchestration should be built only where it creates a real experimental or product advantage.

Preserve the principle:

> Inference chooses; deterministic code validates and executes.

Deterministic code should retain authority over permissions, state changes, side effects, experiment configuration, and evaluation rules.

## Experiment-first discipline

Claims should be earned through controlled experiments.

Separate, where possible:

- what information is selected;
- how it is represented;
- who receives it;
- how it is retrieved;
- how execution is scheduled.

Do not attribute gains from one factor to another.

Use strong baselines.

Do not compare a new method only against intentionally verbose prompts, weak JSON, or poorly configured frameworks.

Negative results are valid.

If simple/native methods perform best, preserve that result rather than weakening the baseline.

## Inspectability and provenance

Experiments should remain inspectable.

Where relevant, preserve enough information to reconstruct:

- experiment/task definition;
- model/provider/version where available;
- harness/runtime;
- skills/tools;
- representation strategy;
- source/artifact versions;
- outputs and evaluations;
- cost/latency measurements;
- failure and recovery behavior.

Do not claim access to hidden reasoning or internal model state when it is not available.

## Backend capability before UI assumptions

Do not freeze UI terminology, layout, navigation, graph representations, or configuration modes unless explicitly requested.

The backend should expose enough structured information for different clients or views later.

## Repository cleanup policy

This repository should not retain obsolete material merely because it once mattered.

During migration or audit work, inspect every tracked file and classify it as:

- **keep** — directly relevant to the new platform/research direction;
- **adapt** — reusable with bounded changes;
- **archive externally only if necessary** — historical reference that should not remain active;
- **delete** — obsolete, duplicative, misleading, or context-polluting.

Prefer deletion when Git history already preserves the old material.

Specifically remove or replace stale project-control material that no longer governs the project, including old:

- `MEMORY.md` or equivalent memory/context files;
- implementation plans for the previous orchestrator;
- completed or obsolete triage/audit documents;
- stale task queues;
- old milestone instructions;
- unused presets/configuration;
- legacy architecture documents;
- research notes that no longer inform active experiments;
- tests and fixtures for deleted behavior.

Do not keep a file solely because deleting it feels risky. Keep it only if it has a concrete role in the new project.

Retain repository essentials such as licensing, build metadata, dependency metadata, CI configuration, and reusable code only when still correct and useful.

After cleanup, repository documentation must not give conflicting instructions about the old orchestrator.

## Open-source role

The repository is intended to remain public unless explicitly changed later.

Open-source code should support reproducibility, inspection, contribution of experiments/adapters, and independent reruns.

Do not assume that every future hosted or commercial feature must also be open-source.

Do not design monetization into the core architecture prematurely.

## Venture-project standard

The immediate standard is a strong university venture/research project, not a mature startup.

Judge progress primarily by:

- technical depth;
- falsifiability;
- quality of prototype;
- reproducibility;
- differentiation from close prior art;
- usefulness to developers/researchers;
- compelling demonstrations;
- feasibility;
- future product optionality.

Revenue, renewal, CAC, gross margin, and enterprise procurement are downstream questions.

A strong open-source project, benchmark, useful research result, or widely reusable testing platform is a valid intermediate success.

## Research discipline

Research should reduce blind spots, not silently redefine the project.

Use this authority chain:

research
→ candidate hypothesis/change
→ experiment/evidence
→ human review
→ accepted project decision
→ implementation

For substantial architectural changes, ask:

1. What existing assumption is being challenged?
2. What evidence would make the current design regrettable later?
3. Must this be decided now?
4. How difficult is it to reverse?
5. Can it remain adapter-local or policy-level?
6. Does it improve the actual experiment/product, or only architectural elegance?

Do not reinterpret every new paper, model, protocol, or framework as a reason to reshape the project.

Prefer, in order:

1. use an existing abstraction;
2. add an adapter or policy;
3. add an extension point;
4. change generic persisted contracts only when evidence shows meaningful future regret.

## Preserve future optionality

The project should remain capable of supporting materially different experiments and systems, including:

- single-agent and multi-agent systems;
- different models/providers;
- different harnesses/runtimes;
- tools and skills;
- artifact/reference workflows;
- different representation strategies;
- later embodied-agent experiments.

Do not let the first successful prototype define the entire project.

## Git delivery

For implementation work, stay in the current checkout.

Before committing:

- run relevant validation;
- inspect `git status`;
- inspect the final diff;
- ensure deleted legacy material is intentional;
- ensure no stale documentation still points to removed contracts.

Commit only passing, intended changes with a concise task-specific message.

Push only when `origin` exists and the user has authorized pushing. Never rewrite existing history destructively.
