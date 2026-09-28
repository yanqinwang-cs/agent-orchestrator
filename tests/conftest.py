from pathlib import Path

import pytest

from orchestrator.config import ApplicationConfig, load_shipped_configuration, repository_root


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return repository_root()


@pytest.fixture(scope="session")
def app_config(repo_root: Path) -> ApplicationConfig:
    return load_shipped_configuration(repo_root)
