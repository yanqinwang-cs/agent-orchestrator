#!/usr/bin/env python3
"""Check basic TOML references as a lightweight supplement to typed config validation."""

from __future__ import annotations

from pathlib import Path
import tomllib


def check(root: Path) -> tuple[int, int, int]:
    configs = {}
    for path in sorted(root.rglob("*.toml")):
        with path.open("rb") as source:
            configs[path.relative_to(root).as_posix()] = tomllib.load(source)
    agents = configs["presets/agents.toml"]["agents"]
    profiles = {profile["id"]: profile for profile in agents}
    if len(profiles) != len(agents):
        raise ValueError("Duplicate AgentProfile IDs")
    for profile in agents:
        if profile["backend"] not in configs["config/backends.toml"]["backends"]:
            raise ValueError(f"Unknown backend in {profile['id']}")
    workflow_count = 0
    for name, workflow in configs.items():
        if not name.startswith("presets/workflows/"):
            continue
        workflow_count += 1
        stages = {stage["id"]: stage for stage in workflow["stages"]}
        if len(stages) != len(workflow["stages"]):
            raise ValueError(f"Duplicate stage in {name}")
        complete: set[str] = set()
        active: set[str] = set()

        def visit(stage_id: str) -> None:
            if stage_id in active:
                raise ValueError(f"Dependency cycle in {name}: {stage_id}")
            if stage_id in complete:
                return
            if stage_id not in stages:
                raise ValueError(f"Missing stage in {name}: {stage_id}")
            active.add(stage_id)
            for dependency in stages[stage_id]["depends_on"]:
                visit(dependency)
            active.remove(stage_id)
            complete.add(stage_id)

        def output_exists(reference: str) -> bool:
            source, _, output = reference.partition(".")
            return source in stages and output in stages[source]["required_outputs"]

        for stage in stages.values():
            visit(stage["id"])
            if stage["kind"] == "worker":
                if not 1 <= stage["min_workers"] <= stage["max_workers"]:
                    raise ValueError(f"Invalid slot bounds in {name}: {stage['id']}")
                if stage["max_workers"] > workflow["max_parallelism"]:
                    raise ValueError(f"Slot exceeds run cap in {name}: {stage['id']}")
                allowed = stage["allowed_profiles"]
                if stage["default_profile"] not in allowed:
                    raise ValueError(f"Invalid default profile in {name}: {stage['id']}")
                for profile_id in allowed:
                    if profile_id not in profiles or profile_id not in workflow["allowed_profiles"]:
                        raise ValueError(f"Unknown or disallowed profile: {profile_id}")
                    if not set(stage["required_outputs"]) <= set(profiles[profile_id]["required_outputs"]):
                        raise ValueError(f"Incompatible profile outputs in {name}: {profile_id}")
            for reference in stage["inputs"]:
                if reference in {"task", "project.revision"}:
                    continue
                if reference.startswith("selected."):
                    key = reference.split(".", 1)[1]
                    branches = workflow.get("branch_outputs", {})
                    if not branches or not all(key in branch and output_exists(branch[key]) for branch in branches.values()):
                        raise ValueError(f"Invalid branch binding in {name}: {reference}")
                elif not output_exists(reference):
                    raise ValueError(f"Missing input output in {name}: {reference}")
        for reference in workflow["required_outputs"]:
            if not output_exists(reference):
                raise ValueError(f"Missing completion output in {name}: {reference}")
        for redirect in workflow["allowed_redirects"]:
            destination = stages[redirect["stage"]]
            if destination.get("slot_kind") != "select_one":
                raise ValueError(f"Redirect requires select-one stage in {name}")
            if not set(redirect["allowed_profiles"]) <= set(destination["allowed_profiles"]):
                raise ValueError(f"Invalid redirect recipients in {name}")
    return len(configs), len(profiles), workflow_count


if __name__ == "__main__":
    counts = check(Path(__file__).resolve().parents[1])
    print(f"Checked {counts[0]} TOML files, {counts[1]} agents and {counts[2]} workflows.")
    print("Syntax and basic cross-references passed; run validate-config for typed validation.")
