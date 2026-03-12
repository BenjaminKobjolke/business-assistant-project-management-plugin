"""Workflow management service."""

from __future__ import annotations

import json

from .constants import ERR_WORKFLOW_NOT_FOUND, ERR_WORKFLOW_SYNONYM_NOT_FOUND
from .database import PmDatabase, PmWorkflow


class WorkflowService:
    """CRUD operations for workflows and synonyms."""

    def __init__(self, db: PmDatabase) -> None:
        self._db = db

    def add_workflow(self, name: str, instructions: str) -> str:
        """Add a new workflow. Returns confirmation message."""
        try:
            workflow = self._db.add_workflow(name=name, instructions=instructions)
            return f"Workflow '{workflow.name}' created."
        except Exception as e:
            return f"Error creating workflow: {e}"

    def find_workflow(self, reference: str) -> PmWorkflow | None:
        """Find a workflow by name or synonym (case-insensitive)."""
        return self._db.find_workflow_by_name_or_synonym(reference)

    def update_workflow(self, name: str, instructions: str) -> str:
        """Update workflow instructions. Returns confirmation message."""
        if self._db.update_workflow(name, instructions):
            return f"Workflow '{name}' updated."
        return ERR_WORKFLOW_NOT_FOUND.format(reference=name)

    def delete_workflow(self, name: str) -> str:
        """Delete a workflow and its synonyms. Returns confirmation message."""
        if self._db.delete_workflow(name):
            return f"Workflow '{name}' deleted."
        return ERR_WORKFLOW_NOT_FOUND.format(reference=name)

    def add_synonym(self, workflow_name: str, synonym: str) -> str:
        """Add a synonym for a workflow. Returns confirmation message."""
        workflow = self._db.get_workflow_by_name(workflow_name)
        if not workflow:
            return ERR_WORKFLOW_NOT_FOUND.format(reference=workflow_name)
        try:
            self._db.add_workflow_synonym(workflow.id, synonym)
            return f"Synonym '{synonym}' added for workflow '{workflow.name}'."
        except Exception as e:
            return f"Error adding synonym: {e}"

    def remove_synonym(self, synonym: str) -> str:
        """Remove a workflow synonym. Returns confirmation message."""
        if self._db.delete_workflow_synonym(synonym):
            return f"Synonym '{synonym}' removed."
        return ERR_WORKFLOW_SYNONYM_NOT_FOUND.format(synonym=synonym)

    def list_workflows(self) -> str:
        """List all workflows as JSON."""
        workflows = self._db.list_workflows()
        items = []
        for w in workflows:
            item: dict = {
                "name": w.name,
                "instructions": w.instructions,
            }
            synonyms = self._db.get_synonyms_for_workflow(w.id)
            if synonyms:
                item["synonyms"] = synonyms
            items.append(item)
        return json.dumps({"workflows": items})

    def format_workflow_details(self, workflow: PmWorkflow) -> str:
        """Format workflow details as a readable string."""
        synonyms = self._db.get_synonyms_for_workflow(workflow.id)
        parts = [f"Workflow: {workflow.name}"]
        parts.append(f"Instructions: {workflow.instructions}")
        if synonyms:
            parts.append(f"Synonyms: {', '.join(synonyms)}")
        return "\n".join(parts)

    def get_workflow_instructions(self, reference: str) -> str:
        """Get workflow instructions by name or synonym."""
        workflow = self._db.find_workflow_by_name_or_synonym(reference)
        if not workflow:
            return ERR_WORKFLOW_NOT_FOUND.format(reference=reference)
        return workflow.instructions
