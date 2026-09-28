"""Small Milestone 1 CLI for config inspection; no worker execution exists."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from orchestrator import __version__
from orchestrator.config import ConfigLoadError, validate_config_file
from orchestrator.validation import ConfigValidationError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-orchestrator",
        description=(
            "Validate Agent Orchestrator configuration. "
            "Worker execution and UI are not implemented yet."
        ),
        epilog="Command usage: agent-orchestrator validate-config PATH",
    )
    parser.add_argument("--version", action="version", version=f"agent-orchestrator {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    validate = subparsers.add_parser("validate-config", help="validate one application TOML file")
    validate.add_argument("path", type=Path, help="path to an application TOML config or overlay")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command is None:
        print("Execution and UI are not implemented yet (Milestone 1).")
        print("Use --help or validate-config PATH to inspect configuration.")
        return 0
    if args.command == "validate-config":
        try:
            summary = validate_config_file(args.path)
        except (ConfigLoadError, ConfigValidationError) as error:
            print(f"invalid configuration:\n{error}", file=sys.stderr)
            return 2
        print(f"Valid {summary}: {args.path}")
        return 0
    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
