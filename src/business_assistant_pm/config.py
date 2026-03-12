"""PM plugin configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .constants import DEFAULT_PM_DB_PATH, ENV_PM_DB_PATH


@dataclass(frozen=True)
class PmSettings:
    """Project management plugin settings."""

    db_path: str = DEFAULT_PM_DB_PATH


def load_pm_settings() -> PmSettings:
    """Load PM settings from environment variables."""
    db_path = os.environ.get(ENV_PM_DB_PATH, DEFAULT_PM_DB_PATH)
    return PmSettings(db_path=db_path)
