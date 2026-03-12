"""Tests for PM plugin configuration."""

from __future__ import annotations

from business_assistant_pm.config import PmSettings, load_pm_settings
from business_assistant_pm.constants import DEFAULT_PM_DB_PATH


class TestPmSettings:
    def test_default_db_path(self) -> None:
        settings = PmSettings()
        assert settings.db_path == DEFAULT_PM_DB_PATH

    def test_custom_db_path(self) -> None:
        settings = PmSettings(db_path="/custom/path.db")
        assert settings.db_path == "/custom/path.db"

    def test_frozen(self) -> None:
        settings = PmSettings()
        try:
            settings.db_path = "other"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass


class TestLoadPmSettings:
    def test_default(self, monkeypatch) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        settings = load_pm_settings()
        assert settings.db_path == DEFAULT_PM_DB_PATH

    def test_from_env(self, monkeypatch) -> None:
        monkeypatch.setenv("PM_DB_PATH", "/env/pm.db")
        settings = load_pm_settings()
        assert settings.db_path == "/env/pm.db"
