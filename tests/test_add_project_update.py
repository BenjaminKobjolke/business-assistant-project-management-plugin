"""Tests for pm_add_project_update tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_OBSIDIAN_NOT_LOADED,
    ERR_PROJECT_NOT_FOUND,
    PLUGIN_DATA_PM_DATABASE,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import pm_add_project_update


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


class TestPmAddProjectUpdate:
    def _setup(self, db: PmDatabase) -> None:
        db.add_project(
            "ACME", obsidian_vault="vault", obsidian_path="Projects/2026/ACME.md",
        )

    @patch("business_assistant_pm.tools_project.datetime")
    def test_happy_path_text_only(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        note_content = "# ACME\n\n## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="ACME", content="Vimeo: https://vimeo.com/123",
        )

        assert "added" in result
        assert "2026-03-17" in result
        obsidian.edit_note.assert_called_once()
        written = obsidian.edit_note.call_args[0][2]
        assert "https://vimeo.com/123" in written

    @patch("business_assistant_pm.tools_project.datetime")
    def test_happy_path_with_files(self, mock_dt, db: PmDatabase, tmp_path) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        # Create a real temp file to copy
        src_file = tmp_path / "img.png"
        src_file.write_bytes(b"fake image")

        # Create vault dir
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        self._setup(db)
        note_content = "## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})
        obsidian.get_vault_path.return_value = str(vault_dir)

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="ACME", file_paths=str(src_file),
        )

        assert "added" in result
        written = obsidian.edit_note.call_args[0][2]
        assert "![[Projects/2026/_resources/img.png]]" in written
        # Verify file was actually copied
        assert (vault_dir / "Projects" / "2026" / "_resources" / "img.png").is_file()

    def test_project_not_found(self, db: PmDatabase) -> None:
        obsidian = MagicMock()
        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(ctx, project_name="Ghost", content="text")
        assert result == ERR_PROJECT_NOT_FOUND.format(reference="Ghost")

    def test_no_obsidian_service(self, db: PmDatabase) -> None:
        self._setup(db)
        ctx = _make_ctx(db, obsidian_service=None)
        result = pm_add_project_update(ctx, project_name="ACME", content="text")
        assert result == ERR_OBSIDIAN_NOT_LOADED

    def test_no_obsidian_link(self, db: PmDatabase) -> None:
        db.add_project("NoLink")
        obsidian = MagicMock()
        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(ctx, project_name="NoLink", content="text")
        assert "no Obsidian note linked" in result

    @patch("business_assistant_pm.tools_project.datetime")
    def test_finds_by_synonym(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        project = db.get_project_by_name("ACME")
        db.add_synonym(project.id, "acme corp")

        note_content = "## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="acme corp", content="Update via synonym",
        )
        assert "added" in result

    @patch("business_assistant_pm.tools_project.datetime")
    def test_multiline_content(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        note_content = "## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="ACME", content="Line 1\nLine 2\nLine 3",
        )
        assert "added" in result
        written = obsidian.edit_note.call_args[0][2]
        assert "Line 1" in written
        assert "Line 2" in written
        assert "Line 3" in written

    @patch("business_assistant_pm.tools_project.datetime")
    def test_read_note_failure(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        obsidian = MagicMock()
        obsidian.read_note.side_effect = RuntimeError("read failed")

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(ctx, project_name="ACME", content="text")
        assert "ERROR" in result

    @patch("business_assistant_pm.tools_project.datetime")
    def test_file_not_found_warning(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        note_content = "## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})
        obsidian.get_vault_path.return_value = "D:/Vault"

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="ACME",
            content="Some text",
            file_paths="/nonexistent/file.png",
        )
        # Should still succeed for text but warn about the file
        assert "added" in result
        assert "File not found" in result

    @patch("business_assistant_pm.tools_project.datetime")
    def test_creates_section_if_missing(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "2026-03-17"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        note_content = "# ACME Project\n\nSome content here.\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        ctx = _make_ctx(db, obsidian)
        result = pm_add_project_update(
            ctx, project_name="ACME", content="First update",
        )
        assert "added" in result
        written = obsidian.edit_note.call_args[0][2]
        assert "## Project Updates" in written
        assert "2026-03-17" in written
        assert "First update" in written
