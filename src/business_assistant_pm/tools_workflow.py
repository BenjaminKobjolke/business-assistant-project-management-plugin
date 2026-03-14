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


def pm_manage_workflow(
    ctx: RunContext[Deps],
    action: str,
    name: str = "",
    instructions: str = "",
    synonym: str = "",
) -> str:
    """Manage workflows. action: create, update, delete, list, add_synonym, remove_synonym.

    Args:
        action: Operation to perform (create, update, delete, list, add_synonym, remove_synonym).
        name: Workflow name (required for create, update, delete, add_synonym).
        instructions: AI instructions (required for create, update). For create, may include
            comma-separated synonyms in the synonym parameter.
        synonym: Synonym phrase (required for add_synonym, remove_synonym).
            For create, optional comma-separated alternative trigger phrases.
    """
    logger.info("pm_manage_workflow: action=%r name=%r", action, name)
    db = _get_db(ctx)
    svc = WorkflowService(db)

    if action == "create":
        result = svc.add_workflow(name, instructions)
        synonym_results = []
        if synonym:
            for s in (s.strip() for s in synonym.split(",") if s.strip()):
                synonym_results.append(svc.add_synonym(name, s))
        parts = [result]
        parts.extend(synonym_results)
        return "\n".join(parts)

    if action == "update":
        return svc.update_workflow(name, instructions)

    if action == "delete":
        return svc.delete_workflow(name)

    if action == "list":
        return svc.list_workflows()

    if action == "add_synonym":
        return svc.add_synonym(name, synonym)

    if action == "remove_synonym":
        return svc.remove_synonym(synonym)

    valid = "create, update, delete, list, add_synonym, remove_synonym"
    return f"ERROR: Unknown action '{action}'. Valid: {valid}."


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
