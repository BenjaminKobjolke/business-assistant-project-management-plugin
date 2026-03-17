"""Tests for pm_set_deadlines_list, pm_get_deadlines, and pm_add_deadline tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import (
    ERR_DEADLINES_LIST_NOT_FOUND,
    ERR_DEADLINES_LIST_NOT_SET,
    ERR_RTM_NOT_LOADED,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_DEADLINES_LIST,
)
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_settings import (
    pm_add_deadline,
    pm_get_deadlines,
    pm_set_deadlines_list,
)


def _make_ctx(
    db: PmDatabase,
    rtm_service: object | None = None,
) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if rtm_service is not None:
        plugin_data["rtm_service"] = rtm_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmSetDeadlinesList:
    def test_stores_setting(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_set_deadlines_list(ctx, "deadlines")
        assert "deadlines" in result
        assert db.get_setting(SETTING_DEADLINES_LIST) == "deadlines"

    def test_overwrites_existing(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "old-list")
        ctx = _make_ctx(db)
        result = pm_set_deadlines_list(ctx, "new-list")
        assert "new-list" in result
        assert db.get_setting(SETTING_DEADLINES_LIST) == "new-list"


class TestPmGetDeadlines:
    def test_not_configured(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_get_deadlines(ctx)
        assert result == ERR_DEADLINES_LIST_NOT_SET

    def test_no_rtm_service(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        ctx = _make_ctx(db, rtm_service=None)
        result = pm_get_deadlines(ctx)
        assert result == ERR_RTM_NOT_LOADED

    def test_success(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        rtm = MagicMock()
        rtm.list_tasks.return_value = json.dumps(
            {"tasks": [{"name": "Ship v2", "due": "2026-03-20"}]}
        )
        ctx = _make_ctx(db, rtm)
        result = pm_get_deadlines(ctx)
        assert "Ship v2" in result
        rtm.list_tasks.assert_called_once_with(
            'status:incomplete AND list:"deadlines"'
        )

    def test_empty_results(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        rtm = MagicMock()
        rtm.list_tasks.return_value = "No tasks found."
        ctx = _make_ctx(db, rtm)
        result = pm_get_deadlines(ctx)
        assert result == "No tasks found."


class TestPmAddDeadline:
    def test_not_configured(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_add_deadline(ctx, "Ship v2")
        assert result == ERR_DEADLINES_LIST_NOT_SET

    def test_no_rtm_service(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        ctx = _make_ctx(db, rtm_service=None)
        result = pm_add_deadline(ctx, "Ship v2")
        assert result == ERR_RTM_NOT_LOADED

    def test_simple_add(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "123", "name": "deadlines", "smart": False}]}
        )
        rtm.add_task.return_value = "Task added: 'Ship v2 !2 ^tomorrow'"
        ctx = _make_ctx(db, rtm)
        result = pm_add_deadline(ctx, "Ship v2")
        assert "Task added" in result
        rtm.add_task.assert_called_once()
        call_args = rtm.add_task.call_args
        assert "Ship v2" in call_args[0][0]
        assert call_args[1]["list_id"] == "123"

    def test_with_project_tag(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        db.add_project("ACME", rtm_tag="#acme")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "123", "name": "deadlines", "smart": False}]}
        )
        rtm.add_task.return_value = "Task added: 'Ship v2 !2 ^tomorrow #acme'"
        ctx = _make_ctx(db, rtm)
        result = pm_add_deadline(ctx, "Ship v2", project="ACME")
        assert "Task added" in result
        smart_name = rtm.add_task.call_args[0][0]
        assert "#acme" in smart_name

    def test_project_none_skips_tag(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        db.add_project("ACME", rtm_tag="#acme")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "123", "name": "deadlines", "smart": False}]}
        )
        rtm.add_task.return_value = "Task added: 'Ship v2 !2 ^tomorrow'"
        ctx = _make_ctx(db, rtm)
        pm_add_deadline(ctx, "Ship v2", project="none")
        smart_name = rtm.add_task.call_args[0][0]
        assert "#acme" not in smart_name

    def test_list_not_found(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "999", "name": "Inbox", "smart": False}]}
        )
        ctx = _make_ctx(db, rtm)
        result = pm_add_deadline(ctx, "Ship v2")
        assert result == ERR_DEADLINES_LIST_NOT_FOUND.format(
            list_name="deadlines"
        )

    def test_custom_priority_and_due(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "123", "name": "deadlines", "smart": False}]}
        )
        rtm.add_task.return_value = "Task added: 'Urgent !1 ^2026-04-01'"
        ctx = _make_ctx(db, rtm)
        pm_add_deadline(
            ctx, "Urgent", due="2026-04-01", priority="1"
        )
        smart_name = rtm.add_task.call_args[0][0]
        assert "!1" in smart_name
        assert "^2026-04-01" in smart_name

    def test_default_tag_appended(self, db: PmDatabase) -> None:
        db.set_setting(SETTING_DEADLINES_LIST, "deadlines")
        db.set_setting("rtm_default_tag", "#work")
        rtm = MagicMock()
        rtm.list_lists.return_value = json.dumps(
            {"lists": [{"_id": "123", "name": "deadlines", "smart": False}]}
        )
        rtm.add_task.return_value = "Task added"
        ctx = _make_ctx(db, rtm)
        pm_add_deadline(ctx, "Review PR")
        smart_name = rtm.add_task.call_args[0][0]
        assert "#work" in smart_name
