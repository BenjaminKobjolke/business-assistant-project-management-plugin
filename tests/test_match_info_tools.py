"""Tests for match info tool functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_project import (
    pm_add_project_match_info,
    pm_list_project_match_info,
    pm_remove_project_match_info,
)


def _make_ctx(
    db: PmDatabase,
    obsidian_service: object | None = None,
) -> RunContext[Deps]:
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    if obsidian_service is not None:
        plugin_data["obsidian_service"] = obsidian_service
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmAddProjectMatchInfo:
    def test_happy_path(self, db: PmDatabase) -> None:
        db.add_project("ACME")
        ctx = _make_ctx(db)
        result = pm_add_project_match_info(ctx, "ACME", "email_domain", "acme.com")
        assert "added" in result
        assert "acme.com" in result

    def test_invalid_type(self, db: PmDatabase) -> None:
        db.add_project("ACME")
        ctx = _make_ctx(db)
        result = pm_add_project_match_info(ctx, "ACME", "invalid_type", "value")
        assert "ERROR" in result
        assert "Invalid rule type" in result

    def test_project_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_add_project_match_info(ctx, "Ghost", "email_domain", "x.com")
        assert "not found" in result

    def test_updates_obsidian(self, db: PmDatabase) -> None:
        db.add_project(
            "ACME",
            obsidian_vault="vault",
            obsidian_path="notes/acme.md",
        )
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": "# ACME\n"})
        ctx = _make_ctx(db, obsidian_service=obsidian)

        pm_add_project_match_info(ctx, "ACME", "email_domain", "acme.com")
        obsidian.edit_note.assert_called_once()

    def test_no_obsidian_no_error(self, db: PmDatabase) -> None:
        db.add_project("ACME")
        ctx = _make_ctx(db)
        result = pm_add_project_match_info(ctx, "ACME", "keyword", "test")
        assert "added" in result


class TestPmRemoveProjectMatchInfo:
    def test_happy_path(self, db: PmDatabase) -> None:
        project = db.add_project("ACME")
        db.add_match_rule(project.id, "email_domain", "acme.com")
        ctx = _make_ctx(db)
        result = pm_remove_project_match_info(ctx, "ACME", "email_domain", "acme.com")
        assert "removed" in result

    def test_not_found(self, db: PmDatabase) -> None:
        db.add_project("ACME")
        ctx = _make_ctx(db)
        result = pm_remove_project_match_info(ctx, "ACME", "email_domain", "nope.com")
        assert "not found" in result

    def test_updates_obsidian(self, db: PmDatabase) -> None:
        project = db.add_project(
            "ACME",
            obsidian_vault="vault",
            obsidian_path="notes/acme.md",
        )
        db.add_match_rule(project.id, "email_domain", "acme.com")
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": "# ACME\n"})
        ctx = _make_ctx(db, obsidian_service=obsidian)

        pm_remove_project_match_info(ctx, "ACME", "email_domain", "acme.com")
        obsidian.edit_note.assert_called_once()


class TestPmListProjectMatchInfo:
    def test_with_rules(self, db: PmDatabase) -> None:
        project = db.add_project("ACME")
        db.add_match_rule(project.id, "email_domain", "acme.com")
        db.add_match_rule(project.id, "keyword", "test")
        ctx = _make_ctx(db)
        result = json.loads(pm_list_project_match_info(ctx, "ACME"))
        assert result["project"] == "ACME"
        assert "acme.com" in result["match_rules"]["email_domain"]
        assert "test" in result["match_rules"]["keyword"]

    def test_empty_rules(self, db: PmDatabase) -> None:
        db.add_project("ACME")
        ctx = _make_ctx(db)
        result = json.loads(pm_list_project_match_info(ctx, "ACME"))
        assert result["project"] == "ACME"
        assert result["match_rules"] == {}

    def test_project_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_list_project_match_info(ctx, "Ghost")
        assert "not found" in result
