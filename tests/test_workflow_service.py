"""Tests for WorkflowService."""

from __future__ import annotations

import json

from business_assistant_pm.database import PmDatabase
from business_assistant_pm.workflow_service import WorkflowService


class TestWorkflowService:
    def test_add_workflow(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.add_workflow("Inbox Zero", "Step 1: Check emails")
        assert "created" in result

    def test_add_duplicate_workflow(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Unique", "instructions")
        result = svc.add_workflow("Unique", "instructions")
        assert "Error" in result

    def test_find_workflow_by_name(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("FindMe", "instructions")
        workflow = svc.find_workflow("FindMe")
        assert workflow is not None
        assert workflow.name == "FindMe"

    def test_find_workflow_by_synonym(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Full Name", "instructions")
        svc.add_synonym("Full Name", "alias")
        workflow = svc.find_workflow("alias")
        assert workflow is not None
        assert workflow.name == "Full Name"

    def test_find_workflow_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        assert svc.find_workflow("nope") is None

    def test_update_workflow(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Updatable", "old")
        result = svc.update_workflow("Updatable", "new")
        assert "updated" in result

    def test_update_workflow_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.update_workflow("Ghost", "new")
        assert "not found" in result

    def test_delete_workflow(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Deletable", "instructions")
        result = svc.delete_workflow("Deletable")
        assert "deleted" in result

    def test_delete_workflow_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.delete_workflow("Ghost")
        assert "not found" in result

    def test_add_synonym(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Flow", "instructions")
        result = svc.add_synonym("Flow", "shortname")
        assert "added" in result

    def test_add_synonym_workflow_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.add_synonym("Ghost", "alias")
        assert "not found" in result

    def test_remove_synonym(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Flow", "instructions")
        svc.add_synonym("Flow", "removable")
        result = svc.remove_synonym("removable")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.remove_synonym("ghost")
        assert "not found" in result

    def test_list_workflows(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("A", "instructions A")
        svc.add_workflow("B", "instructions B")
        result = svc.list_workflows()
        data = json.loads(result)
        assert len(data["workflows"]) == 2
        assert data["workflows"][0]["name"] == "A"
        assert data["workflows"][0]["instructions"] == "instructions A"

    def test_list_workflows_with_synonyms(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Flow", "instructions")
        svc.add_synonym("Flow", "alias")
        result = svc.list_workflows()
        data = json.loads(result)
        assert data["workflows"][0]["synonyms"] == ["alias"]

    def test_format_workflow_details(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        workflow = db.add_workflow("Test", "Do the thing")
        result = svc.format_workflow_details(workflow)
        assert "Workflow: Test" in result
        assert "Instructions: Do the thing" in result

    def test_format_workflow_details_with_synonyms(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        workflow = db.add_workflow("Test", "Do the thing")
        db.add_workflow_synonym(workflow.id, "alias")
        result = svc.format_workflow_details(workflow)
        assert "Synonyms: alias" in result

    def test_get_workflow_instructions(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Flow", "Step 1: Do X\nStep 2: Do Y")
        result = svc.get_workflow_instructions("Flow")
        assert result == "Step 1: Do X\nStep 2: Do Y"

    def test_get_workflow_instructions_by_synonym(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        svc.add_workflow("Flow", "Step 1: Do X")
        svc.add_synonym("Flow", "my alias")
        result = svc.get_workflow_instructions("my alias")
        assert result == "Step 1: Do X"

    def test_get_workflow_instructions_not_found(self, db: PmDatabase) -> None:
        svc = WorkflowService(db)
        result = svc.get_workflow_instructions("nope")
        assert "not found" in result
