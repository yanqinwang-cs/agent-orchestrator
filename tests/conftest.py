import json
from pathlib import Path

import pytest

from orchestrator.backends.codex import CodexBackend
from orchestrator.config import ApplicationConfig, load_shipped_configuration, repository_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return repository_root()


@pytest.fixture(scope="session")
def app_config(repo_root: Path) -> ApplicationConfig:
    return load_shipped_configuration(repo_root)


@pytest.fixture(autouse=True)
def offline_codex_cli(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the bundled Codex binary probe with the pinned fixture in every default test.

    Running the real binary takes a few seconds and depends on the host, so only tests marked
    ``live`` probe it. The real check lives in test_codex_backend_live.py.
    """
    if request.node.get_closest_marker("live") is not None:
        return
    fixture = json.loads(
        (repository_root() / "tests/fixtures/backends/codex-sdk-0.159.2.json").read_text()
    )
    pinned = (
        "bundled-codex-cli/bin/codex",
        fixture["cli"]["version"],
        fixture["cli"]["sha256"],
    )
    monkeypatch.setattr(CodexBackend, "_inspect_cli", staticmethod(lambda: pinned))
