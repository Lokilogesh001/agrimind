"""Global Pytest Configuration and Test Harness Fixtures for AgriMind."""
from __future__ import annotations

import os
import sys
from pathlib import Path
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Enforce development mode and test overrides during test execution
os.environ["ENVIRONMENT"] = "development"
os.environ["ALLOW_TEST_OVERRIDES"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from observability import database as obs
from data_sources.market import clear_market_cache_for_tests


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Isolate each test execution with clean memory database and cleared external caches."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_TEST_OVERRIDES", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    # Prevent accidental external billable calls during automated test suites
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.delenv("AGMARKNET_BASE_URL", raising=False)

    obs.reset_engine_for_tests()
    obs.init_db()
    clear_market_cache_for_tests()
    yield
    obs.reset_engine_for_tests()
    clear_market_cache_for_tests()
