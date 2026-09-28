#!/usr/bin/env python3
"""Regenerate committed JSON Schemas from the Python contract models."""

from pathlib import Path

from orchestrator.schemas import export_schemas

root = Path(__file__).resolve().parents[1]
for schema_path in export_schemas(root / "schemas"):
    print(schema_path.relative_to(root))
