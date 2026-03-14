"""Tests for workflow tool functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_workflow import (
    pm_manage_workflow,
    pm_run_workflow,
)


def _make_ctx(db: PmDatabase) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmManageWorkflowCreate:
    def test_create(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "create", name="Inbox Zero", instructions="Step 1")
        assert "created" in result

    def test_create_with_synonyms(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(
            ctx, "create", name="Inbox Zero", instructions="Step 1",
            synonym="inbox aufraeumen, clean inbox",
        )
        assert "created" in result
        assert "inbox aufraeumen" in result
        assert "clean inbox" in result

    def test_create_duplicate(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Unique", instructions="x")
        result = pm_manage_workflow(ctx, "create", name="Unique", instructions="x")
        assert "Error" in result


class TestPmManageWorkflowUpdate:
    def test_update(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Flow", instructions="old")
        result = pm_manage_workflow(ctx, "update", name="Flow", instructions="new")
        assert "updated" in result

    def test_update_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "update", name="Ghost", instructions="new")
        assert "not found" in result


class TestPmManageWorkflowDelete:
    def test_delete(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Deletable", instructions="x")
        result = pm_manage_workflow(ctx, "delete", name="Deletable")
        assert "deleted" in result

    def test_delete_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "delete", name="Ghost")
        assert "not found" in result


class TestPmManageWorkflowSynonyms:
    def test_add_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Flow", instructions="x")
        result = pm_manage_workflow(ctx, "add_synonym", name="Flow", synonym="alias")
        assert "added" in result

    def test_add_synonym_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "add_synonym", name="Ghost", synonym="alias")
        assert "not found" in result

    def test_remove_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Flow", instructions="x")
        pm_manage_workflow(ctx, "add_synonym", name="Flow", synonym="removable")
        result = pm_manage_workflow(ctx, "remove_synonym", synonym="removable")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "remove_synonym", synonym="ghost")
        assert "not found" in result


class TestPmManageWorkflowList:
    def test_list_empty(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "list")
        data = json.loads(result)
        assert data["workflows"] == []

    def test_list_with_workflows(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="A", instructions="a")
        pm_manage_workflow(ctx, "create", name="B", instructions="b")
        result = pm_manage_workflow(ctx, "list")
        data = json.loads(result)
        assert len(data["workflows"]) == 2


class TestPmManageWorkflowInvalidAction:
    def test_unknown_action(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_manage_workflow(ctx, "invalid")
        assert "ERROR" in result
        assert "Unknown action" in result


class TestPmRunWorkflow:
    def test_run_by_name(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(
            ctx, "create", name="Inbox Zero",
            instructions="Step 1: Check emails\nStep 2: Archive",
        )
        result = pm_run_workflow(ctx, "Inbox Zero")
        assert "Workflow: Inbox Zero" in result
        assert "Step 1: Check emails" in result
        assert "Step 2: Archive" in result

    def test_run_by_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_manage_workflow(ctx, "create", name="Inbox Zero", instructions="Step 1")
        pm_manage_workflow(ctx, "add_synonym", name="Inbox Zero", synonym="inbox aufraeumen")
        result = pm_run_workflow(ctx, "inbox aufraeumen")
        assert "Workflow: Inbox Zero" in result
        assert "Step 1" in result

    def test_run_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_run_workflow(ctx, "nonexistent")
        assert "not found" in result
