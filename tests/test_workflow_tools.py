"""Tests for workflow tool functions."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tools_workflow import (
    pm_add_workflow,
    pm_add_workflow_synonym,
    pm_delete_workflow,
    pm_list_workflows,
    pm_remove_workflow_synonym,
    pm_run_workflow,
    pm_update_workflow,
)


def _make_ctx(db: PmDatabase) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmAddWorkflow:
    def test_add_workflow(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_add_workflow(ctx, "Inbox Zero", "Step 1: Check emails")
        assert "created" in result

    def test_add_workflow_with_synonyms(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_add_workflow(
            ctx, "Inbox Zero", "Step 1: Check emails",
            synonyms="inbox aufraeumen, clean inbox",
        )
        assert "created" in result
        assert "inbox aufraeumen" in result
        assert "clean inbox" in result

    def test_add_duplicate_workflow(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Unique", "instructions")
        result = pm_add_workflow(ctx, "Unique", "instructions")
        assert "Error" in result


class TestPmUpdateWorkflow:
    def test_update_workflow(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Flow", "old")
        result = pm_update_workflow(ctx, "Flow", "new")
        assert "updated" in result

    def test_update_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_update_workflow(ctx, "Ghost", "new")
        assert "not found" in result


class TestPmDeleteWorkflow:
    def test_delete_workflow(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Deletable", "instructions")
        result = pm_delete_workflow(ctx, "Deletable")
        assert "deleted" in result

    def test_delete_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_delete_workflow(ctx, "Ghost")
        assert "not found" in result


class TestPmAddWorkflowSynonym:
    def test_add_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Flow", "instructions")
        result = pm_add_workflow_synonym(ctx, "Flow", "alias")
        assert "added" in result

    def test_add_synonym_workflow_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_add_workflow_synonym(ctx, "Ghost", "alias")
        assert "not found" in result


class TestPmRemoveWorkflowSynonym:
    def test_remove_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Flow", "instructions")
        pm_add_workflow_synonym(ctx, "Flow", "removable")
        result = pm_remove_workflow_synonym(ctx, "removable")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_remove_workflow_synonym(ctx, "ghost")
        assert "not found" in result


class TestPmListWorkflows:
    def test_list_empty(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_list_workflows(ctx)
        data = json.loads(result)
        assert data["workflows"] == []

    def test_list_with_workflows(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "A", "instructions A")
        pm_add_workflow(ctx, "B", "instructions B")
        result = pm_list_workflows(ctx)
        data = json.loads(result)
        assert len(data["workflows"]) == 2


class TestPmRunWorkflow:
    def test_run_workflow_by_name(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Inbox Zero", "Step 1: Check emails\nStep 2: Archive")
        result = pm_run_workflow(ctx, "Inbox Zero")
        assert "Workflow: Inbox Zero" in result
        assert "Step 1: Check emails" in result
        assert "Step 2: Archive" in result

    def test_run_workflow_by_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        pm_add_workflow(ctx, "Inbox Zero", "Step 1: Check emails")
        pm_add_workflow_synonym(ctx, "Inbox Zero", "inbox aufraeumen")
        result = pm_run_workflow(ctx, "inbox aufraeumen")
        assert "Workflow: Inbox Zero" in result
        assert "Step 1: Check emails" in result

    def test_run_workflow_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_run_workflow(ctx, "nonexistent")
        assert "not found" in result
