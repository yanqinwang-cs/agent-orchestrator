#!/usr/bin/env python3
"""Launch a repository development preset without changing user configuration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tomllib


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    with (root / "config/development.toml").open("rb") as source:
        presets = tomllib.load(source)["presets"]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("preset", choices=sorted(presets))
    task_group = parser.add_mutually_exclusive_group(required=True)
    task_group.add_argument("--task")
    task_group.add_argument("--task-file", type=Path)
    parser.add_argument("--model", help="An available Codex model ID; default: user config")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        task = args.task if args.task_file is None else args.task_file.read_text()
    except OSError as error:
        parser.error(str(error))
    if not task or not task.strip():
        parser.error("Task must not be empty.")
    preset = presets[args.preset]
    prompt = "\n".join(
        [
            f"Development preset: {args.preset}",
            preset["purpose"],
            "Read AGENTS.md before editing.",
            "Tool intentions: " + ", ".join(preset["tools"]),
            "Expected outputs: " + "; ".join(preset["outputs"]),
            "Stopping condition: " + preset["stop"],
            "Optional skills, only if available and relevant: "
            + (", ".join(preset["skills"]) or "none")
            + ". Missing skills do not block the task.",
            "",
            "Task:",
            task,
        ]
    )
    binary = shutil.which("codex")
    if binary is None and not args.dry_run:
        parser.error("Codex CLI was not found on PATH. Install it before launching.")
    command = [
        binary or "codex",
        "-C", str(root),
        "-s", preset["sandbox"],
        "-a", "on-request",
        "-c", 'approvals_reviewer="user"',
        "-c", "model_reasoning_effort=" + json.dumps(preset["effort"]),
        "-c", "web_search=" + json.dumps(preset["web_search"]),
    ]
    if args.model:
        command.extend(["--model", args.model])
    command.append(prompt)
    if args.dry_run:
        print(json.dumps({"cwd": str(root), "argv": command}, indent=2))
        return 0
    return subprocess.run(command, cwd=root, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
