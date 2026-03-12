"""Shared test fixtures for PM plugin tests."""

from __future__ import annotations

import pytest

from business_assistant_pm.config import PmSettings
from business_assistant_pm.database import PmDatabase


@pytest.fixture()
def pm_settings() -> PmSettings:
    """PM settings for testing."""
    return PmSettings(db_path=":memory:")


@pytest.fixture()
def db() -> PmDatabase:
    """In-memory database for testing."""
    return PmDatabase(":memory:")
