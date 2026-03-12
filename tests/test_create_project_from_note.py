"""Tests for pm_create_project_from_note tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_OBSIDIAN_NOT_LOADED,
    ERR_SETTING_MISSING,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_PROJECT_VAULT,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import pm_create_project_from_note


def _make_ctx(
    db: PmDatabase,
    obsidian_service: object | None = None,
) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if obsidian_service is not None:
        plugin_data["obsidian_service"] = obsidian_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


NOTE_CONTENT = (
    "# Project\n\n"
    "**Kundenprojektname**\n\nACME Corp\n\n"
    "**Projektordner**\n\nACME_Folder\n\n"
    "**RTM Tag**\n\n#p_acme\n\n"
    "## Details\n"
)


class TestPmCreateProjectFromNote:
    def _setup_settings(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_PROJECT_VAULT, "XIDA")

    def test_happy_path(self, db: PmDatabase) -> None:
        self._setup_settings(db)

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": NOTE_CONTENT})

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="XD - Projects/2026/acme_project.md",
            project_name="ACME",
        )

        assert "ACME" in result
        assert "created" in result
        assert "RTM tag extracted: #p_acme" in result
        assert "Note linked: XIDA/XD - Projects/2026/acme_project.md" in result
        assert "ACME Corp" in result
        assert "Kundenprojektname" in result
        assert "ACME_Folder" in result
        assert "Projektordner" in result
        assert "acme_project" in result
        assert "filename" in result
        assert "ask the user" in result

        # Verify project registered in DB
        project = db.get_project_by_name("ACME")
        assert project is not None
        assert project.rtm_tag == "#p_acme"
        assert project.obsidian_vault == "XIDA"
        assert project.obsidian_path == "XD - Projects/2026/acme_project.md"
        assert project.project_folder == "ACME_Folder"

    def test_missing_obsidian_service(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        ctx = _make_ctx(db, obsidian_service=None)
        result = pm_create_project_from_note(
            ctx,
            note_path="note.md",
            project_name="Test",
        )
        assert result == ERR_OBSIDIAN_NOT_LOADED

    def test_missing_setting(self, db: PmDatabase) -> None:
        # Don't set project_vault
        obsidian = MagicMock()
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="note.md",
            project_name="Test",
        )
        assert ERR_SETTING_MISSING.format(key=SETTING_PROJECT_VAULT) == result

    def test_note_read_failure(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        obsidian = MagicMock()
        obsidian.read_note.side_effect = RuntimeError("connection failed")
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="note.md",
            project_name="Test",
        )
        assert "ERROR: Failed to read note" in result
        assert "connection failed" in result

    def test_no_rtm_tag(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        content = "# Project\n\n**Kundenprojektname**\n\nSome Corp\n\nNo RTM here\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})
        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="projects/some_project.md",
            project_name="Some",
        )
        assert "created" in result
        assert "No RTM tag found" in result
        # Synonyms still suggested
        assert "Some Corp" in result
        assert "some_project" in result

    def test_no_suggestions(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        content = "**RTM Tag**\n\n#p_bare\n\nNothing else\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})
        ctx = _make_ctx(db, obsidian)
        # Note path is just the project name so filename = project_name
        result = pm_create_project_from_note(
            ctx,
            note_path="Bare.md",
            project_name="Bare",
        )
        assert "created" in result
        assert "RTM tag extracted: #p_bare" in result
        # Filename "Bare" is still a suggestion
        assert "Bare" in result
