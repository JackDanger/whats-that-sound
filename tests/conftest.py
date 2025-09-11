"""Pytest configuration and shared fixtures."""

import os
import pytest

# Silence noisy third-party deprecation warnings in test output
pytest.register_assert_rewrite(__name__)

def pytest_configure(config):
    # Filter deprecations from external libs we don't control
    config.addinivalue_line("filterwarnings", r"ignore:.*websockets\.legacy is deprecated.*:DeprecationWarning")
    config.addinivalue_line("filterwarnings", r"ignore:.*WebSocketServerProtocol is deprecated.*:DeprecationWarning")


@pytest.fixture(scope="session", autouse=True)
def _isolate_sqlite_db(tmp_path_factory):
    """Ensure tests use an isolated SQLite DB path and never the production DB."""
    db_dir = tmp_path_factory.mktemp("wts_db")
    os.environ["WTS_DB_PATH"] = str(db_dir / "tests.sqlite")
    yield
