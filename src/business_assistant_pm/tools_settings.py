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


def pm_settings(
    ctx: RunContext[Deps],
    action: str = "get",
    key: str = "",
    value: str = "",
) -> str:
    """Manage PM settings. action: get (list all), set (store key=value).

    Args:
        action: Operation — get or set.
        key: Setting key (required for set). Common keys: todo_folder, wait_folder,
            rtm_import_email, default_priority, default_due, rtm_default_tag,
            project_vault, project_template_path, project_folder_path.
        value: Setting value (required for set).
    """
    logger.info("pm_settings: action=%r key=%r", action, key)
    db = _get_db(ctx)

    if action == "set":
        db.set_setting(key, value)
        return f"Setting '{key}' set to '{value}'."

    if action == "get":
        settings = db.get_all_settings()
        if not settings:
            return "No settings configured yet."
        return json.dumps({"settings": settings})

    return f"ERROR: Unknown action '{action}'. Valid: get, set."


def pm_tracking(
    ctx: RunContext[Deps],
    action: str = "list",
    tracking_id: str = "",
    status: str = "active",
    delegated_to: str = "",
) -> str:
    """Query tracking records. action: list (with filters), get (by ID).

    Args:
        action: Operation — list or get.
        tracking_id: Tracking record ID (required for get).
        status: Filter by status — active, completed, cancelled (for list).
        delegated_to: Filter by delegate name (for list).
    """
    logger.info("pm_tracking: action=%r tracking_id=%r", action, tracking_id)
    db = _get_db(ctx)

    if action == "get":
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

    if action == "list":
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

    return f"ERROR: Unknown action '{action}'. Valid: list, get."
