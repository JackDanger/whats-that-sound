"""Pytest configuration and shared fixtures."""

import pytest

# Silence noisy third-party deprecation warnings in test output
pytest.register_assert_rewrite(__name__)

def pytest_configure(config):
    # Filter deprecations from external libs we don't control
    config.addinivalue_line("filterwarnings", r"ignore:.*websockets\.legacy is deprecated.*:DeprecationWarning")
    config.addinivalue_line("filterwarnings", r"ignore:.*WebSocketServerProtocol is deprecated.*:DeprecationWarning")
