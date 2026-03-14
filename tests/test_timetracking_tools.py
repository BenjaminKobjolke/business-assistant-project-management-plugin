"""Tests for pm_log_time and pm_list_timetracking_projects tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_PROJECT_NO_TIMETRACKING,
    ERR_PROJECT_NOT_FOUND,
    ERR_WORKINGTIMES_NOT_LOADED,
    PLUGIN_DATA_PM_DATABASE,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import pm_list_timetracking_projects, pm_log_time


def _make_ctx(
    db: PmDatabase,
    workingtimes_service: object | None = None,
) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if workingtimes_service is not None:
        plugin_data["workingtimes_service"] = workingtimes_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmLogTime:
    def test_success(self, db: PmDatabase) -> None:
        db.add_project("ACME", timetracking_project_id="tt-123")
        wt = MagicMock()
        wt.add_time.return_value = json.dumps({"status": "ok", "seconds": 3600})
        ctx = _make_ctx(db, wt)
        result = pm_log_time(ctx, "ACME", 3600, "Did work")
        assert "ok" in result
        wt.add_time.assert_called_once_with(
            project_id="tt-123", time_seconds=3600, comment="Did work",
        )

    def test_workingtimes_not_loaded(self, db: PmDatabase) -> None:
        db.add_project("ACME", timetracking_project_id="tt-123")
        ctx = _make_ctx(db, workingtimes_service=None)
        result = pm_log_time(ctx, "ACME", 3600, "work")
        assert result == ERR_WORKINGTIMES_NOT_LOADED

    def test_project_not_found(self, db: PmDatabase) -> None:
        wt = MagicMock()
        ctx = _make_ctx(db, wt)
        result = pm_log_time(ctx, "Nonexistent", 3600, "work")
        assert result == ERR_PROJECT_NOT_FOUND.format(reference="Nonexistent")

    def test_no_timetracking_id(self, db: PmDatabase) -> None:
        db.add_project("NoTT")
        wt = MagicMock()
        ctx = _make_ctx(db, wt)
        result = pm_log_time(ctx, "NoTT", 3600, "work")
        assert result == ERR_PROJECT_NO_TIMETRACKING.format(name="NoTT")

    def test_with_adjust_time(self, db: PmDatabase) -> None:
        db.add_project("ACME", timetracking_project_id="tt-123")
        wt = MagicMock()
        wt.add_time.return_value = json.dumps({"status": "ok"})
        ctx = _make_ctx(db, wt)
        result = pm_log_time(ctx, "ACME", 3600, "work", adjust_time="-1h")
        wt.add_time.assert_called_once_with(
            project_id="tt-123", time_seconds=3600, comment="work", adjust_time="-1h",
        )
        assert "ok" in result

    def test_finds_project_by_synonym(self, db: PmDatabase) -> None:
        project = db.add_project("ACME Corp", timetracking_project_id="tt-789")
        db.add_synonym(project.id, "acme")
        wt = MagicMock()
        wt.add_time.return_value = json.dumps({"status": "ok"})
        ctx = _make_ctx(db, wt)
        result = pm_log_time(ctx, "acme", 1800, "quick task")
        assert "ok" in result
        wt.add_time.assert_called_once_with(
            project_id="tt-789", time_seconds=1800, comment="quick task",
        )


class TestPmListTimetrackingProjects:
    def test_success(self, db: PmDatabase) -> None:
        wt = MagicMock()
        wt.list_projects.return_value = json.dumps(
            {"projects": [{"id": "tt-1", "name": "Project 1"}]},
        )
        ctx = _make_ctx(db, wt)
        result = pm_list_timetracking_projects(ctx)
        assert "Project 1" in result
        wt.list_projects.assert_called_once()

    def test_workingtimes_not_loaded(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db, workingtimes_service=None)
        result = pm_list_timetracking_projects(ctx)
        assert result == ERR_WORKINGTIMES_NOT_LOADED
