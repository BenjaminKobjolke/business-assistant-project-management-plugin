"""PydanticAI tool functions for workflow management."""

from __future__ import annotations

import logging

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import ERR_WORKFLOW_NOT_FOUND, PLUGIN_DATA_PM_DATABASE
from .database import PmDatabase
from .workflow_service import WorkflowService

logger = logging.getLogger(__name__)


def _get_db(ctx: RunContext[Deps]) -> PmDatabase:
    return ctx.deps.plugin_data[PLUGIN_DATA_PM_DATABASE]


def pm_add_workflow(
    ctx: RunContext[Deps],
    name: str,
    instructions: str,
    synonyms: str = "",
) -> str:
    """Create a reusable named workflow with AI instructions.

    Args:
        name: Display name for the workflow.
        instructions: The AI instructions describing the multi-step process.
        synonyms: Optional comma-separated alternative trigger phrases.
    """
    logger.info("pm_add_workflow: name=%r", name)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    result = svc.add_workflow(name, instructions)

    synonym_results = []
    if synonyms:
        for synonym in (s.strip() for s in synonyms.split(",") if s.strip()):
            synonym_results.append(svc.add_synonym(name, synonym))

    parts = [result]
    parts.extend(synonym_results)
    return "\n".join(parts)


def pm_update_workflow(
    ctx: RunContext[Deps],
    name: str,
    instructions: str,
) -> str:
    """Update the instructions of an existing workflow.

    Args:
        name: Name of the workflow to update.
        instructions: The new AI instructions.
    """
    logger.info("pm_update_workflow: name=%r", name)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    return svc.update_workflow(name, instructions)


def pm_delete_workflow(ctx: RunContext[Deps], name: str) -> str:
    """Delete a workflow and all its synonyms.

    Args:
        name: Name of the workflow to delete.
    """
    logger.info("pm_delete_workflow: name=%r", name)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    return svc.delete_workflow(name)


def pm_add_workflow_synonym(
    ctx: RunContext[Deps],
    workflow_name: str,
    synonym: str,
) -> str:
    """Add an alternative trigger phrase for a workflow.

    Args:
        workflow_name: Name of the workflow.
        synonym: Alternative phrase to trigger this workflow.
    """
    logger.info("pm_add_workflow_synonym: workflow=%r synonym=%r", workflow_name, synonym)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    return svc.add_synonym(workflow_name, synonym)


def pm_remove_workflow_synonym(ctx: RunContext[Deps], synonym: str) -> str:
    """Remove an alternative trigger phrase for a workflow.

    Args:
        synonym: The synonym to remove.
    """
    logger.info("pm_remove_workflow_synonym: synonym=%r", synonym)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    return svc.remove_synonym(synonym)


def pm_list_workflows(ctx: RunContext[Deps]) -> str:
    """List all workflows as JSON."""
    logger.info("pm_list_workflows")
    db = _get_db(ctx)
    svc = WorkflowService(db)
    return svc.list_workflows()


def pm_run_workflow(ctx: RunContext[Deps], reference: str) -> str:
    """Look up a workflow by name or synonym and return its instructions.

    The returned instructions should be followed step by step using available tools.

    Args:
        reference: Workflow name or synonym to look up.
    """
    logger.info("pm_run_workflow: reference=%r", reference)
    db = _get_db(ctx)
    svc = WorkflowService(db)
    workflow = svc.find_workflow(reference)
    if not workflow:
        return ERR_WORKFLOW_NOT_FOUND.format(reference=reference)
    return (
        f"## Workflow: {workflow.name}\n\n"
        f"Follow these instructions step by step:\n\n{workflow.instructions}"
    )
