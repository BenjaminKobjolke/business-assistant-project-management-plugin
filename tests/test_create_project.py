"""Tests for pm_create_project tool and related service functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_FILESYSTEM_NOT_LOADED,
    ERR_NOTE_CREATION_FAILED,
    ERR_OBSIDIAN_NOT_LOADED,
    ERR_SETTING_MISSING,
    ERR_TEMPLATE_READ_FAILED,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_PROJECT_FILES_BASE_PATH,
    SETTING_PROJECT_FOLDER_PATH,
    SETTING_PROJECT_TEMPLATE_PATH,
    SETTING_PROJECT_VAULT,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.project_service import ProjectService
from business_assistant_pm.tools_project import pm_create_project

# --- Service-level tests ---


class TestFillTemplateFields:
    def test_fills_both_fields(self) -> None:
        template = (
            "# Project\n\n"
            "**Kundenprojektname**\n\n"
            "**RTM Tag**\n\n"
            "## Details\n"
        )
        result = ProjectService.fill_template_fields(template, "ACME Corp", "#p_acme")
        assert "**Kundenprojektname**\nACME Corp\n" in result
        assert "**RTM Tag**\n#p_acme\n" in result

    def test_preserves_surrounding_content(self) -> None:
        template = (
            "Header\n\n"
            "**Kundenprojektname**\n\n"
            "Middle\n\n"
            "**RTM Tag**\n\n"
            "Footer\n"
        )
        result = ProjectService.fill_template_fields(template, "Test", "#tag")
        assert result.startswith("Header\n")
        assert "Middle\n" in result
        assert result.endswith("Footer\n")

    def test_missing_headings_returns_unchanged(self) -> None:
        template = "No headings here\nJust plain text\n"
        result = ProjectService.fill_template_fields(template, "Name", "#tag")
        assert result == template

    def test_fills_projektordner(self) -> None:
        template = (
            "# Project\n\n"
            "**Kundenprojektname**\n\n"
            "**RTM Tag**\n\n"
            "**Projektordner**\n\n"
            "## Details\n"
        )
        result = ProjectService.fill_template_fields(
            template, "ACME Corp", "#p_acme", "ACME_Folder",
        )
        assert "**Projektordner**\nACME_Folder\n" in result

    def test_no_projektordner_leaves_unchanged(self) -> None:
        template = (
            "**Kundenprojektname**\n\n"
            "**RTM Tag**\n\n"
            "**Projektordner**\n\n"
        )
        result = ProjectService.fill_template_fields(template, "Name", "#tag")
        # Projektordner heading stays with blank line
        assert "**Projektordner**\n\n" in result

    def test_only_kundenprojektname_present(self) -> None:
        template = "**Kundenprojektname**\n\nSome other text\n"
        result = ProjectService.fill_template_fields(template, "Filled", "#missing")
        assert "**Kundenprojektname**\nFilled\n" in result
        # RTM Tag heading not present, so no substitution
        assert "#missing" not in result


class TestBuildProjectNotePath:
    @patch("business_assistant_pm.project_service.datetime")
    def test_correct_year_and_filename(self, mock_dt) -> None:
        mock_now = MagicMock()
        mock_now.year = 2026
        mock_dt.now.return_value = mock_now
        path = ProjectService.build_project_note_path("XD - Projects", "my_project")
        assert path == "XD - Projects/2026/my_project.md"

    @patch("business_assistant_pm.project_service.datetime")
    def test_different_year(self, mock_dt) -> None:
        mock_now = MagicMock()
        mock_now.year = 2027
        mock_dt.now.return_value = mock_now
        path = ProjectService.build_project_note_path("Projects", "test")
        assert path == "Projects/2027/test.md"


# --- Tool-level tests ---


def _make_ctx(
    db: PmDatabase,
    obsidian_service: object | None = None,
    filesystem_service: object | None = None,
) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if obsidian_service is not None:
        plugin_data["obsidian_service"] = obsidian_service
    if filesystem_service is not None:
        plugin_data["filesystem_service"] = filesystem_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


TEMPLATE_CONTENT = (
    "# Projekt\n\n"
    "**Kundenprojektname**\n\n"
    "**RTM Tag**\n\n"
    "## Aufgaben\n"
)


class TestPmCreateProjectTool:
    def _setup_settings(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_PROJECT_VAULT, "XIDA")
        db.set_setting(
            SETTING_PROJECT_TEMPLATE_PATH,
            "XD - Templates/Neues Projekt - Projektvorlage.md",
        )
        db.set_setting(SETTING_PROJECT_FOLDER_PATH, "XD - Projects")

    def test_happy_path(self, db: PmDatabase) -> None:
        self._setup_settings(db)

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="acme_project",
            customer_name="ACME Corp",
            rtm_tag="#p_acme",
            project_name="ACME",
            synonyms="acme, acme corp",
        )

        assert "ACME" in result
        assert "created" in result
        assert "Note created at:" in result

        # Verify note was created with filled content
        call_args = obsidian.create_note.call_args
        created_content = call_args[0][2]
        assert "ACME Corp" in created_content
        assert "#p_acme" in created_content

        # Verify synonyms were added
        project = db.find_project_by_name_or_synonym("acme")
        assert project is not None
        assert project.name == "ACME"

    def test_missing_obsidian_service(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        ctx = _make_ctx(db, obsidian_service=None)
        result = pm_create_project(
            ctx,
            filename="test",
            customer_name="Test",
            rtm_tag="#t",
            project_name="Test",
        )
        assert result == ERR_OBSIDIAN_NOT_LOADED

    @pytest.mark.parametrize(
        "missing_key",
        [SETTING_PROJECT_VAULT, SETTING_PROJECT_TEMPLATE_PATH, SETTING_PROJECT_FOLDER_PATH],
    )
    def test_missing_setting(self, db: PmDatabase, missing_key: str) -> None:
        # Set all settings except the missing one
        all_settings = {
            SETTING_PROJECT_VAULT: "XIDA",
            SETTING_PROJECT_TEMPLATE_PATH: "template.md",
            SETTING_PROJECT_FOLDER_PATH: "Projects",
        }
        for key, value in all_settings.items():
            if key != missing_key:
                db.set_setting(key, value)

        obsidian = MagicMock()
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="test",
            customer_name="Test",
            rtm_tag="#t",
            project_name="Test",
        )
        assert ERR_SETTING_MISSING.format(key=missing_key) == result

    def test_template_read_failure(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        obsidian = MagicMock()
        obsidian.read_note.side_effect = RuntimeError("connection failed")
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="test",
            customer_name="Test",
            rtm_tag="#t",
            project_name="Test",
        )
        assert result == ERR_TEMPLATE_READ_FAILED.format(error="connection failed")

    def test_note_creation_failure(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.side_effect = RuntimeError("already exists")
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="test",
            customer_name="Test",
            rtm_tag="#t",
            project_name="Test",
        )
        assert result == ERR_NOTE_CREATION_FAILED.format(error="already exists")

    def test_no_synonyms(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="solo",
            customer_name="Solo Inc",
            rtm_tag="#p_solo",
            project_name="Solo",
        )
        assert "created" in result
        # No synonyms registered
        synonyms = db.get_synonyms_for_project(
            db.get_project_by_name("Solo").id,
        )
        assert synonyms == []

    def test_project_folder_created_on_disk(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"

        filesystem = MagicMock()
        filesystem.create_directory.return_value = '{"success": true}'

        ctx = _make_ctx(db, obsidian, filesystem_service=filesystem)
        result = pm_create_project(
            ctx,
            filename="acme",
            customer_name="ACME",
            rtm_tag="#p_acme",
            project_name="ACME",
            project_folder="ACME_Folder",
        )

        assert "Folder created: Y:/ACME_Folder" in result
        filesystem.create_directory.assert_called_once_with("Y:/ACME_Folder")

    def test_project_folder_missing_filesystem_service(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="acme",
            customer_name="ACME",
            rtm_tag="#p_acme",
            project_name="ACME",
            project_folder="ACME_Folder",
        )

        assert result == ERR_FILESYSTEM_NOT_LOADED

    def test_project_folder_missing_base_path(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        # Do NOT set SETTING_PROJECT_FILES_BASE_PATH

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"

        filesystem = MagicMock()
        ctx = _make_ctx(db, obsidian, filesystem_service=filesystem)
        result = pm_create_project(
            ctx,
            filename="acme",
            customer_name="ACME",
            rtm_tag="#p_acme",
            project_name="ACME",
            project_folder="ACME_Folder",
        )

        assert result == ERR_SETTING_MISSING.format(key=SETTING_PROJECT_FILES_BASE_PATH)

    def test_no_project_folder_skips_creation(self, db: PmDatabase) -> None:
        self._setup_settings(db)

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": TEMPLATE_CONTENT})
        obsidian.create_note.return_value = "ok"

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project(
            ctx,
            filename="nofolder",
            customer_name="NoFolder Inc",
            rtm_tag="#p_nofolder",
            project_name="NoFolder",
        )

        assert "created" in result
        assert "Folder created" not in result
