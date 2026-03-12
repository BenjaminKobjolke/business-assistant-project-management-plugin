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
    SETTING_PROJECT_FILES_BASE_PATH,
    SETTING_PROJECT_VAULT,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import pm_create_project_from_note


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


NOTE_CONTENT = (
    "# Project\n\n"
    "**Kundenprojektname**\n\nACME Corp\n\n"
    "**Projektordner**\n\nACME_Folder\n\n"
    "**RTM Tag**\n\n#p_acme\n\n"
    "## Details\n"
)

NOTE_CONTENT_WITH_MATCHING = (
    "# Project\n\n"
    "**Kundenprojektname**\n\nACME Corp\n\n"
    "**Projektordner**\n\nACME_Folder\n\n"
    "**RTM Tag**\n\n#p_acme\n\n"
    "**Matching**\n"
    "email_domains: acme.com, acme.de\n"
    "project_numbers: 260086\n"
    "keywords: ACME Widget\n"
    "\n**Other**\n"
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

    def test_project_folder_created_on_disk(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": NOTE_CONTENT})

        filesystem = MagicMock()
        filesystem.create_directory.return_value = '{"success": true}'

        ctx = _make_ctx(db, obsidian, filesystem_service=filesystem)
        result = pm_create_project_from_note(
            ctx,
            note_path="XD - Projects/2026/acme.md",
            project_name="ACME",
        )

        assert "Folder created: Y:/ACME_Folder" in result
        filesystem.create_directory.assert_called_once_with("Y:/ACME_Folder")

    def test_note_with_matching_section(self, db: PmDatabase) -> None:
        self._setup_settings(db)

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps(
            {"content": NOTE_CONTENT_WITH_MATCHING},
        )

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="XD - Projects/2026/acme.md",
            project_name="ACME",
        )

        assert "Match rules imported: 4" in result

        # Verify rules in DB
        project = db.get_project_by_name("ACME")
        assert project is not None
        rules = db.get_match_rules_for_project(project.id)
        rule_types = {r.rule_type for r in rules}
        assert "email_domain" in rule_types
        assert "project_number" in rule_types
        assert "keyword" in rule_types
        values = {r.value for r in rules}
        assert "acme.com" in values
        assert "260086" in values

    def test_note_without_matching_section(self, db: PmDatabase) -> None:
        self._setup_settings(db)

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": NOTE_CONTENT})

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="XD - Projects/2026/acme.md",
            project_name="ACME",
        )

        assert "created" in result
        assert "Match rules imported" not in result
        project = db.get_project_by_name("ACME")
        assert project is not None
        assert len(db.get_match_rules_for_project(project.id)) == 0

    def test_project_folder_no_filesystem_skips_gracefully(self, db: PmDatabase) -> None:
        self._setup_settings(db)
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")

        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": NOTE_CONTENT})

        ctx = _make_ctx(db, obsidian)
        result = pm_create_project_from_note(
            ctx,
            note_path="XD - Projects/2026/acme.md",
            project_name="ACME",
        )

        assert "created" in result
        assert "Folder created" not in result
