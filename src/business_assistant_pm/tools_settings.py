"""PydanticAI tool functions for settings and tracking queries."""

from __future__ import annotations

import json
import logging

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import (
    DEFAULT_DUE,
    DEFAULT_PRIORITY,
    ERR_DEADLINES_LIST_NOT_FOUND,
    ERR_DEADLINES_LIST_NOT_SET,
    ERR_RTM_NOT_LOADED,
    ERR_TRACKING_NOT_FOUND,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_DEADLINES_LIST,
    SETTING_DEFAULT_DUE,
    SETTING_DEFAULT_PRIORITY,
    SETTING_RTM_DEFAULT_TAG,
)
from .database import PmDatabase
from .plugin_helpers import _get_rtm_service, _get_setting_or_default
from .project_service import ProjectService
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


def pm_set_deadlines_list(ctx: RunContext[Deps], list_name: str) -> str:
    """Set which RTM list to use for deadlines.

    Args:
        list_name: The name of the RTM list (e.g. "deadlines").
    """
    logger.info("pm_set_deadlines_list: list_name=%r", list_name)
    db = _get_db(ctx)
    db.set_setting(SETTING_DEADLINES_LIST, list_name)
    return f"Deadlines list set to '{list_name}'."


def pm_get_deadlines(ctx: RunContext[Deps]) -> str:
    """Retrieve upcoming deadlines from the configured RTM deadlines list.

    Returns incomplete tasks sorted by due date.
    """
    logger.info("pm_get_deadlines")
    db = _get_db(ctx)
    list_name = db.get_setting(SETTING_DEADLINES_LIST)
    if not list_name:
        return ERR_DEADLINES_LIST_NOT_SET

    rtm_service = _get_rtm_service(ctx)
    if not rtm_service:
        return ERR_RTM_NOT_LOADED

    filter_str = f'status:incomplete AND list:"{list_name}"'
    return rtm_service.list_tasks(filter_str)


def pm_add_deadline(
    ctx: RunContext[Deps],
    task_name: str,
    due: str = "",
    priority: str = "",
    project: str = "",
) -> str:
    """Add a deadline to the configured RTM deadlines list.

    Args:
        task_name: Name/description of the deadline.
        due: Due date (e.g. "tomorrow", "2026-03-20"). Uses default if empty.
        priority: Priority 1-3. Uses default if empty.
        project: Project name/synonym. Adds RTM tag if matched. Use "none" or "" to skip.
    """
    logger.info(
        "pm_add_deadline: task=%r due=%r priority=%r project=%r",
        task_name, due, priority, project,
    )
    db = _get_db(ctx)
    list_name = db.get_setting(SETTING_DEADLINES_LIST)
    if not list_name:
        return ERR_DEADLINES_LIST_NOT_SET

    rtm_service = _get_rtm_service(ctx)
    if not rtm_service:
        return ERR_RTM_NOT_LOADED

    effective_priority = priority or _get_setting_or_default(
        db, SETTING_DEFAULT_PRIORITY, DEFAULT_PRIORITY
    )
    effective_due = due or _get_setting_or_default(
        db, SETTING_DEFAULT_DUE, DEFAULT_DUE
    )

    smart_parts = [task_name, f"!{effective_priority}", f"^{effective_due}"]

    if project and project.lower() != "none":
        proj_svc = ProjectService(db)
        proj = proj_svc.find_project(project)
        if proj and proj.rtm_tag:
            smart_parts.append(proj.rtm_tag)

    default_tag = db.get_setting(SETTING_RTM_DEFAULT_TAG)
    if default_tag:
        smart_parts.append(default_tag)

    smart_name = " ".join(smart_parts)

    lists_json = rtm_service.list_lists()
    list_id = _resolve_list_id(lists_json, list_name)
    if not list_id:
        return ERR_DEADLINES_LIST_NOT_FOUND.format(list_name=list_name)

    return rtm_service.add_task(smart_name, list_id=list_id)


def _resolve_list_id(lists_json: str, list_name: str) -> str | None:
    """Resolve an RTM list name to its ID."""
    try:
        data = json.loads(lists_json)
        for lst in data.get("lists", []):
            if lst["name"].lower() == list_name.lower():
                return lst["_id"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None
