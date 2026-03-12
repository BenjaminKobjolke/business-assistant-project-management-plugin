"""Tests for email-to-project matching engine."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.project_service import ProjectService
from business_assistant_pm.tools_project import pm_match_email_to_project


def _make_ctx(db: PmDatabase) -> RunContext[Deps]:
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestMatchEmailToProject:
    def test_match_by_email_domain(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "email_domain", "acme.com")

        result = json.loads(svc.match_email_to_project("user@acme.com", "Hello"))
        assert result["project_name"] == "ACME"
        assert result["score"] == 100
        assert result["matched_by"] == "email_domain"

    def test_match_by_contact(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "contact", "john@acme.com")

        result = json.loads(svc.match_email_to_project("john@acme.com", "Hello"))
        assert result["project_name"] == "ACME"
        assert result["matched_by"] == "contact"

    def test_match_by_project_number(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "project_number", "260086")

        result = json.loads(
            svc.match_email_to_project("anyone@x.com", "RE: 260086 - Invoice"),
        )
        assert result["project_name"] == "ACME"
        assert result["matched_by"] == "project_number"

    def test_match_by_keyword(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("GameDev")
        project = db.get_project_by_name("GameDev")
        assert project is not None
        db.add_match_rule(project.id, "keyword", "jump n run")

        result = json.loads(
            svc.match_email_to_project("dev@studio.com", "Update on Jump n Run game"),
        )
        assert result["project_name"] == "GameDev"
        assert result["matched_by"] == "keyword"
        assert result["score"] == 50

    def test_match_by_project_name_in_subject(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")

        result = json.loads(
            svc.match_email_to_project("anyone@x.com", "Update on ACME project"),
        )
        assert result["project_name"] == "ACME"
        assert result["matched_by"] == "name"
        assert result["score"] == 80

    def test_match_by_synonym_in_subject(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("MyProject")
        svc.add_synonym("MyProject", "widget co")

        result = json.loads(
            svc.match_email_to_project("x@x.com", "News from widget co"),
        )
        assert result["project_name"] == "MyProject"
        assert result["matched_by"] == "synonym"

    def test_score_accumulation(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "email_domain", "acme.com")
        db.add_match_rule(project.id, "keyword", "invoice")

        result = json.loads(
            svc.match_email_to_project("user@acme.com", "Invoice for ACME"),
        )
        assert result["project_name"] == "ACME"
        # domain(100) + keyword(50) + name(80) = 230
        assert result["score"] == 230

    def test_best_match_wins(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("LowScore")
        svc.add_project("HighScore")

        low = db.get_project_by_name("LowScore")
        high = db.get_project_by_name("HighScore")
        assert low is not None
        assert high is not None
        db.add_match_rule(low.id, "keyword", "shared")
        db.add_match_rule(high.id, "email_domain", "high.com")
        db.add_match_rule(high.id, "keyword", "shared")

        result = json.loads(
            svc.match_email_to_project("user@high.com", "About shared topic"),
        )
        assert result["project_name"] == "HighScore"

    def test_case_insensitive_matching(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "contact", "john@acme.com")

        result = json.loads(
            svc.match_email_to_project("JOHN@ACME.COM", "Hello"),
        )
        assert result["project_name"] == "ACME"

    def test_no_match(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("ACME")

        result = json.loads(
            svc.match_email_to_project("stranger@unknown.com", "Random topic"),
        )
        assert result["status"] == "no_match"


class TestMatchEmailTool:
    def test_tool_returns_json(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        db.add_project("ACME")
        project = db.get_project_by_name("ACME")
        assert project is not None
        db.add_match_rule(project.id, "email_domain", "acme.com")

        result = pm_match_email_to_project(ctx, "user@acme.com", "Hello")
        data = json.loads(result)
        assert data["project_name"] == "ACME"

    def test_tool_no_match(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_match_email_to_project(ctx, "x@x.com", "Nothing")
        data = json.loads(result)
        assert data["status"] == "no_match"
