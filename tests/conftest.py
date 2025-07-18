"""Pytest configuration and shared fixtures."""

import sys
import pytest
from unittest.mock import MagicMock

# Mock llama_cpp module before any imports
sys.modules["llama_cpp"] = MagicMock()
