import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routesense import config  # noqa: E402


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Each test gets its own SQLite file, so tests never touch the demo database."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    yield
