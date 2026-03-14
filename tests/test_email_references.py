"""Tests for email reference CRUD and tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_tracking import pm_link_email_to_project, pm_list_email_references


def _make_ctx(db: PmDatabase) -> RunContext[Deps]:
    deps = MagicMock(spec=Deps)
    deps.plugin_data = {PLUGIN_DATA_PM_DATABASE: db}
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestEmailReferencesDatabase:
    def test_add_and_list(self, db: PmDatabase) -> None:
        project = db.add_project(name="TestProject")
        db.add_email_reference(
            project_id=project.id,
            project_name=project.name,
            email_subject="Invoice 123",
            email_from="sender@example.com",
            email_date="2026-03-14",
            email_folder="INBOX",
            note="Important invoice",
        )

        refs = db.list_email_references("TestProject")
        assert len(refs) == 1
        assert refs[0].email_subject == "Invoice 123"
        assert refs[0].email_from == "sender@example.com"
        assert refs[0].email_date == "2026-03-14"
        assert refs[0].note == "Important invoice"

    def test_list_empty(self, db: PmDatabase) -> None:
        refs = db.list_email_references("NonExistent")
        assert refs == []

    def test_list_case_insensitive(self, db: PmDatabase) -> None:
        project = db.add_project(name="MyProject")
        db.add_email_reference(
            project_id=project.id,
            project_name=project.name,
            email_subject="Test",
            email_from="a@b.com",
        )

        refs = db.list_email_references("myproject")
        assert len(refs) == 1

    def test_delete(self, db: PmDatabase) -> None:
        project = db.add_project(name="DelProject")
        ref = db.add_email_reference(
            project_id=project.id,
            project_name=project.name,
            email_subject="Delete me",
            email_from="x@y.com",
        )

        assert db.delete_email_reference(ref.id) is True
        assert db.list_email_references("DelProject") == []

    def test_delete_not_found(self, db: PmDatabase) -> None:
        assert db.delete_email_reference(9999) is False


class TestEmailReferenceTools:
    def test_link_success(self, db: PmDatabase) -> None:
        db.add_project(name="Alpha")
        ctx = _make_ctx(db)

        result = pm_link_email_to_project(
            ctx,
            project_name="Alpha",
            email_subject="Contract Draft",
            email_from="client@corp.com",
            email_date="2026-03-14",
            folder="INBOX",
            note="Final version",
        )

        assert "Email linked to project 'Alpha'" in result
        assert "Contract Draft" in result
        assert "client@corp.com" in result

    def test_link_project_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)

        result = pm_link_email_to_project(
            ctx,
            project_name="NoSuchProject",
            email_subject="Test",
            email_from="a@b.com",
        )

        assert "ERROR" in result
        assert "NoSuchProject" in result

    def test_list_references(self, db: PmDatabase) -> None:
        project = db.add_project(name="Beta")
        db.add_email_reference(
            project_id=project.id,
            project_name=project.name,
            email_subject="Ref 1",
            email_from="one@test.com",
        )
        db.add_email_reference(
            project_id=project.id,
            project_name=project.name,
            email_subject="Ref 2",
            email_from="two@test.com",
            note="Follow up",
        )
        ctx = _make_ctx(db)

        result = pm_list_email_references(ctx, project_name="Beta")
        data = json.loads(result)

        assert len(data["references"]) == 2
        assert data["references"][0]["email_subject"] == "Ref 1"
        assert data["references"][1]["note"] == "Follow up"
