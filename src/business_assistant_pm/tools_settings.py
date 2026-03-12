"""PydanticAI tool functions for settings and tracking queries."""

from __future__ import annotations

import json
import logging

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import ERR_TRACKING_NOT_FOUND, PLUGIN_DATA_PM_DATABASE
from .database import PmDatabase
from .tracking_service import TrackingService

logger = logging.getLogger(__name__)


def _get_db(ctx: RunContext[Deps]) -> PmDatabase:
    return ctx.deps.plugin_data[PLUGIN_DATA_PM_DATABASE]


def pm_set_setting(ctx: RunContext[Deps], key: str, value: str) -> str:
    """Configure a runtime setting (persisted in database).

    Common settings:
    - todo_folder: IMAP folder for self-todos
    - wait_folder: IMAP folder for delegations
    - rtm_import_email: BCC address for RTM email-to-task
    - default_priority: Default task priority (1-3)
    - default_due: Default due date (e.g., 'tomorrow')
    - rtm_default_tag: Default RTM tag for all tasks
    - project_vault: Obsidian vault name for project templates
    - project_template_path: Vault-relative path to project template MD file
    - project_folder_path: Vault-relative path to projects folder (year auto-appended)
    """
    logger.info("pm_set_setting: key=%r value=%r", key, value)
    db = _get_db(ctx)
    db.set_setting(key, value)
    return f"Setting '{key}' set to '{value}'."


def pm_get_settings(ctx: RunContext[Deps]) -> str:
    """View all current PM settings."""
    logger.info("pm_get_settings")
    db = _get_db(ctx)
    settings = db.get_all_settings()
    if not settings:
        return "No settings configured yet."
    return json.dumps({"settings": settings})


def pm_list_tracking(
    ctx: RunContext[Deps],
    status: str = "active",
    delegated_to: str = "",
) -> str:
    """List tracked email-task records.

    Filter by status ('active', 'completed', 'cancelled')
    and optionally by delegate name.
    """
    logger.info("pm_list_tracking: status=%r delegated_to=%r", status, delegated_to)
    db = _get_db(ctx)
    records = db.list_tracking(status=status, delegated_to=delegated_to)
    if not records:
        return f"No {status} tracking records found."
    items = [
        {
            "tracking_id": r.tracking_id,
            "task_name": r.task_name,
            "email_subject": r.email_subject,
            "email_from": r.email_from,
            "email_folder": r.email_folder,
            "delegated_to": r.delegated_to or "",
            "project": r.project_name or "",
            "status": r.status,
        }
        for r in records
    ]
    return json.dumps({"tracking": items})


def pm_get_tracking(ctx: RunContext[Deps], tracking_id: str) -> str:
    """Get details of a specific tracking record."""
    logger.info("pm_get_tracking: tracking_id=%r", tracking_id)
    db = _get_db(ctx)
    tracking_svc = TrackingService(db)
    record = tracking_svc.find_by_tracking_id(tracking_id)
    if not record:
        return ERR_TRACKING_NOT_FOUND.format(tracking_id=tracking_id)
    return json.dumps({
        "tracking_id": record.tracking_id,
        "email_id": record.email_id,
        "email_subject": record.email_subject,
        "email_from": record.email_from,
        "email_folder": record.email_folder,
        "task_name": record.task_name,
        "rtm_task_id": record.rtm_task_id or "",
        "delegated_to": record.delegated_to or "",
        "project": record.project_name or "",
        "status": record.status,
        "created_at": str(record.created_at) if record.created_at else "",
        "completed_at": str(record.completed_at) if record.completed_at else "",
    })
