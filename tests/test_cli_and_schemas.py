from pathlib import Path

import pytest

from orchestrator.cli import main
from orchestrator.schemas import SCHEMAS, export_schemas


def test_default_cli_does_not_claim_execution(capsys) -> None:
    assert main([]) == 0
    output = capsys.readouterr().out
    assert "Execution and UI are not implemented yet" in output


def test_cli_validate_config_and_version(repo_root: Path, capsys) -> None:
    assert main(["validate-config", str(repo_root / "config" / "project.example.toml")]) == 0
    assert "Valid project example-project" in capsys.readouterr().out
    with pytest.raises(SystemExit) as result:
        main(["--version"])
    assert result.value.code == 0
    assert "agent-orchestrator 0.1.0" in capsys.readouterr().out


def test_cli_help_is_available(capsys) -> None:
    with pytest.raises(SystemExit) as result:
        main(["--help"])
    assert result.value.code == 0
    assert "validate-config PATH" in capsys.readouterr().out


def test_committed_json_schemas_match_typed_models(repo_root: Path, tmp_path: Path) -> None:
    generated = export_schemas(tmp_path)
    assert len(generated) == len(SCHEMAS)
    for output in generated:
        assert (repo_root / "schemas" / output.name).read_bytes() == output.read_bytes()
