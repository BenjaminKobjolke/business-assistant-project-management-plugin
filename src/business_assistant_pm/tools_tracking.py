"""PydanticAI tool functions for email-task tracking workflows."""

from __future__ import annotations

import json
import logging

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import (
    ACTION_ARCHIVE,
    ACTION_LEAVE,
    ACTION_REPLY_AND_ARCHIVE,
    DEFAULT_DUE,
    DEFAULT_PRIORITY,
    ERR_EMAIL_NOT_LOADED,
    ERR_RTM_NOT_LOADED,
    ERR_TRACKING_NOT_FOUND,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_DEFAULT_DUE,
    SETTING_DEFAULT_PRIORITY,
    SETTING_RTM_DEFAULT_TAG,
    SETTING_TODO_FOLDER,
)
from .database import PmDatabase
from .plugin_helpers import (
    _get_email_service,
    _get_rtm_service,
    _get_setting_or_default,
    _require_setting,
)
from .project_service import ProjectService
from .tracking_service import TrackingService

logger = logging.getLogger(__name__)


def _get_db(ctx: RunContext[Deps]) -> PmDatabase:
    return ctx.deps.plugin_data[PLUGIN_DATA_PM_DATABASE]


def pm_create_todo_from_email(
    ctx: RunContext[Deps],
    email_id: str,
    task_name: str,
    priority: str = "",
    due: str = "",
    tags: str = "",
    folder: str = "INBOX",
    project: str = "",
) -> str:
    """Create an RTM task from an email with tracking.

    Moves the email to the configured todo folder and creates a tracking record.
    Use the project parameter to link to a known project (adds RTM tag automatically).
    """
    logger.info(
        "pm_create_todo_from_email: email_id=%r task=%r folder=%r",
        email_id, task_name, folder,
    )

    rtm_service = _get_rtm_service(ctx)
    if not rtm_service:
        return ERR_RTM_NOT_LOADED

    email_service = _get_email_service(ctx)
    if not email_service:
        return ERR_EMAIL_NOT_LOADED

    db = _get_db(ctx)

    err = _require_setting(db, SETTING_TODO_FOLDER)
    if err:
        return err

    todo_folder = db.get_setting(SETTING_TODO_FOLDER)
    assert todo_folder is not None
    effective_priority = priority or _get_setting_or_default(
        db, SETTING_DEFAULT_PRIORITY, DEFAULT_PRIORITY
    )
    effective_due = due or _get_setting_or_default(db, SETTING_DEFAULT_DUE, DEFAULT_DUE)

    smart_parts = [task_name, f"!{effective_priority}", f"^{effective_due}"]

    project_name = None
    if project:
        proj_svc = ProjectService(db)
        proj = proj_svc.find_project(project)
        if proj and proj.rtm_tag:
            smart_parts.append(proj.rtm_tag)
            project_name = proj.name

    default_tag = db.get_setting(SETTING_RTM_DEFAULT_TAG)
    if default_tag:
        smart_parts.append(default_tag)

    if tags:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                if not tag.startswith("#"):
                    tag = f"#{tag}"
                smart_parts.append(tag)

    smart_name = " ".join(smart_parts)

    email_data = email_service.show_email(email_id, folder)
    email_subject = ""
    email_from = ""
    try:
        parsed = json.loads(email_data)
        email_subject = parsed.get("subject", "")
        email_from = parsed.get("from", "")
    except (json.JSONDecodeError, TypeError):
        pass

    result = rtm_service.add_task(smart_name)
    if result.startswith("Error"):
        return result

    tracking_svc = TrackingService(db)
    tracking_id = tracking_svc.create_tracking(
        email_id=email_id,
        email_folder=todo_folder,
        email_subject=email_subject,
        email_from=email_from,
        task_name=task_name,
        project_name=project_name,
    )

    move_result = email_service.move_email(email_id, todo_folder, source_folder=folder)

    return (
        f"Task created: {task_name}\n"
        f"Email moved to {todo_folder}.\n"
        f"Tracking ID: {tracking_id}\n"
        f"Move result: {move_result}"
    )


def pm_complete_tracked_task(ctx: RunContext[Deps], task_id: str) -> str:
    """Complete a tracked task and show original email info.

    If the task has a tracking record, shows the original email details
    and asks what to do with it. Falls through to normal RTM completion
    if no tracking found.
    """
    logger.info("pm_complete_tracked_task: task_id=%r", task_id)

    rtm_service = _get_rtm_service(ctx)
    if not rtm_service:
        return ERR_RTM_NOT_LOADED

    db = _get_db(ctx)
    tracking_svc = TrackingService(db)
    record = tracking_svc.find_by_rtm_task_id(task_id)

    result = rtm_service.complete_task(task_id)
    if result.startswith("Error"):
        return result

    if record:
        return (
            f"Task completed.\n\n"
            f"This task was linked to an email:\n"
            f"  Subject: {record.email_subject}\n"
            f"  From: {record.email_from}\n"
            f"  Folder: {record.email_folder}\n"
            f"  Tracking ID: {record.tracking_id}\n\n"
            f"What would you like to do with the original email?\n"
            f"- reply_and_archive: Draft a reply and archive\n"
            f"- archive: Just archive it\n"
            f"- leave: Leave it where it is"
        )

    return result


def pm_handle_completed_email(
    ctx: RunContext[Deps],
    tracking_id: str,
    action: str,
    reply_body: str = "",
) -> str:
    """Handle the email after a tracked task is completed.

    Actions: 'archive', 'reply_and_archive', 'leave'.
    """
    logger.info(
        "pm_handle_completed_email: tracking_id=%r action=%r",
        tracking_id, action,
    )

    db = _get_db(ctx)
    tracking_svc = TrackingService(db)
    record = tracking_svc.find_by_tracking_id(tracking_id)

    if not record:
        return ERR_TRACKING_NOT_FOUND.format(tracking_id=tracking_id)

    email_service = _get_email_service(ctx)
    if not email_service:
        return ERR_EMAIL_NOT_LOADED

    results = []

    if action == ACTION_REPLY_AND_ARCHIVE and reply_body:
        reply_result = email_service.draft_reply(
            record.email_id, reply_body, folder=record.email_folder,
        )
        results.append(f"Reply: {reply_result}")

    if action in (ACTION_ARCHIVE, ACTION_REPLY_AND_ARCHIVE):
        done_result = email_service.mark_as_done(
            email_id=record.email_id,
            database=ctx.deps.plugin_data.get("database"),
            folder=record.email_folder,
        )
        results.append(f"Archive: {done_result}")

    if action == ACTION_LEAVE:
        results.append("Email left in current folder.")

    tracking_svc.complete_tracking(tracking_id)
    results.append("Tracking marked as completed.")

    return "\n".join(results)
