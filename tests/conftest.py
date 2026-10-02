import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def _no_live(monkeypatch):
    """Tests never run with the live flag set, whatever the developer's shell has."""
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    yield


@pytest.fixture
def repo_root():
    return ROOT


@pytest.fixture
def chdir_root(monkeypatch):
    monkeypatch.chdir(ROOT)
    yield ROOT


@pytest.fixture
def tmp_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def pytest_configure(config):
    os.environ.setdefault("PYTHONHASHSEED", "0")
