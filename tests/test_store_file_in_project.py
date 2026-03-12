"""Tests for pm_store_file_in_project tool."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_FILESYSTEM_NOT_LOADED,
    ERR_PROJECT_NO_FOLDER,
    ERR_PROJECT_NOT_FOUND,
    ERR_SETTING_MISSING,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_PROJECT_FILES_BASE_PATH,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import pm_store_file_in_project


def _make_ctx(
    db: PmDatabase,
    filesystem_service: object | None = None,
) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if filesystem_service is not None:
        plugin_data["filesystem_service"] = filesystem_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmStoreFileInProject:
    def _setup(self, db: PmDatabase) -> None:
        db.add_project("ACME", project_folder="ACME_Folder")
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")

    @patch("business_assistant_pm.tools_project.datetime")
    def test_happy_path(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20260312"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        fs = MagicMock()
        fs.create_directory.return_value = json.dumps(
            {"path": "Y:/ACME_Folder/Source/20260312_email", "status": "created"},
        )
        fs.copy_file.return_value = json.dumps(
            {
                "source": "/tmp/attachment.pdf",
                "destination": "Y:/ACME_Folder/Source/20260312_email/attachment.pdf",
                "size": 1024,
                "status": "copied",
            },
        )
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx,
            project_name="ACME",
            source_file_path="/tmp/attachment.pdf",
            source_type="email",
        )
        assert "File stored:" in result
        assert "ACME_Folder/Source/20260312_email/attachment.pdf" in result
        fs.create_directory.assert_called_once_with(
            "Y:/ACME_Folder/Source/20260312_email",
        )
        fs.copy_file.assert_called_once_with(
            "/tmp/attachment.pdf",
            "Y:/ACME_Folder/Source/20260312_email/attachment.pdf",
        )

    @patch("business_assistant_pm.tools_project.datetime")
    def test_download_source_type(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20260312"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        fs = MagicMock()
        fs.create_directory.return_value = json.dumps(
            {"path": "Y:/ACME_Folder/Source/20260312_download", "status": "created"},
        )
        fs.copy_file.return_value = json.dumps(
            {"source": "s", "destination": "d", "size": 10, "status": "copied"},
        )
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx,
            project_name="ACME",
            source_file_path="/tmp/file.zip",
            source_type="download",
        )
        assert "File stored:" in result
        fs.create_directory.assert_called_once_with(
            "Y:/ACME_Folder/Source/20260312_download",
        )

    def test_finds_project_by_synonym(self, db: PmDatabase) -> None:
        self._setup(db)
        db.add_synonym(db.get_project_by_name("ACME").id, "acme corp")
        fs = MagicMock()
        fs.create_directory.return_value = json.dumps({"status": "created", "path": "x"})
        fs.copy_file.return_value = json.dumps(
            {"source": "s", "destination": "d", "size": 1, "status": "copied"},
        )
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="acme corp", source_file_path="/tmp/f.txt",
        )
        assert "File stored:" in result

    def test_missing_filesystem_service(self, db: PmDatabase) -> None:
        self._setup(db)
        ctx = _make_ctx(db, filesystem_service=None)
        result = pm_store_file_in_project(
            ctx, project_name="ACME", source_file_path="/tmp/f.txt",
        )
        assert result == ERR_FILESYSTEM_NOT_LOADED

    def test_project_not_found(self, db: PmDatabase) -> None:
        self._setup(db)
        fs = MagicMock()
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="Nonexistent", source_file_path="/tmp/f.txt",
        )
        assert result == ERR_PROJECT_NOT_FOUND.format(reference="Nonexistent")

    def test_project_no_folder(self, db: PmDatabase) -> None:
        db.add_project("NoFolder")
        db.set_setting(SETTING_PROJECT_FILES_BASE_PATH, "Y:")
        fs = MagicMock()
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="NoFolder", source_file_path="/tmp/f.txt",
        )
        assert result == ERR_PROJECT_NO_FOLDER.format(name="NoFolder")

    def test_missing_base_path_setting(self, db: PmDatabase) -> None:
        db.add_project("ACME", project_folder="ACME_Folder")
        # Don't set SETTING_PROJECT_FILES_BASE_PATH
        fs = MagicMock()
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="ACME", source_file_path="/tmp/f.txt",
        )
        assert result == ERR_SETTING_MISSING.format(key=SETTING_PROJECT_FILES_BASE_PATH)

    def test_create_directory_error(self, db: PmDatabase) -> None:
        self._setup(db)
        fs = MagicMock()
        fs.create_directory.return_value = (
            "Access denied: path 'Y:/ACME_Folder' is not within allowed directories."
        )
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="ACME", source_file_path="/tmp/f.txt",
        )
        assert "Access denied" in result

    @patch("business_assistant_pm.tools_project.datetime")
    def test_copy_file_error(self, mock_dt, db: PmDatabase) -> None:
        mock_now = MagicMock()
        mock_now.strftime.return_value = "20260312"
        mock_dt.now.return_value = mock_now

        self._setup(db)
        fs = MagicMock()
        fs.create_directory.return_value = json.dumps({"status": "created", "path": "x"})
        fs.copy_file.return_value = "Source file not found: '/tmp/missing.pdf'"
        ctx = _make_ctx(db, fs)
        result = pm_store_file_in_project(
            ctx, project_name="ACME", source_file_path="/tmp/missing.pdf",
        )
        assert "Source file not found" in result
