"""PydanticAI tool functions for delegation workflows."""

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
    ERR_CONTACT_NO_RTM_TAG,
    ERR_CONTACT_NOT_FOUND,
    ERR_EMAIL_NOT_LOADED,
    ERR_TRACKING_NOT_FOUND,
    PLUGIN_DATA_PM_DATABASE,
    SETTING_DEFAULT_DUE,
    SETTING_DEFAULT_PRIORITY,
    SETTING_RTM_DEFAULT_TAG,
    SETTING_RTM_IMPORT_EMAIL,
    SETTING_WAIT_FOLDER,
)
from .database import PmDatabase
from .delegation_service import DelegationService
from .plugin_helpers import (
    _get_email_service,
    _get_setting_or_default,
    _require_setting,
)
from .project_service import ProjectService
from .tracking_service import TrackingService

logger = logging.getLogger(__name__)


def _get_db(ctx: RunContext[Deps]) -> PmDatabase:
    return ctx.deps.plugin_data[PLUGIN_DATA_PM_DATABASE]


def pm_delegate_email(
    ctx: RunContext[Deps],
    email_id: str,
    delegate_name: str,
    topic: str = "",
    priority: str = "",
    due: str = "",
    folder: str = "INBOX",
    project: str = "",
) -> str:
    """Delegate an email task to a contact via draft email with RTM BCC.

    Creates a draft email to the contact with RTM Smart Add subject,
    moves the original email to the wait folder, and creates tracking.
    """
    logger.info(
        "pm_delegate_email: email_id=%r delegate=%r folder=%r",
        email_id, delegate_name, folder,
    )

    email_service = _get_email_service(ctx)
    if not email_service:
        return ERR_EMAIL_NOT_LOADED

    db = _get_db(ctx)

    for key in (SETTING_WAIT_FOLDER, SETTING_RTM_IMPORT_EMAIL):
        err = _require_setting(db, key)
        if err:
            return err

    wait_folder = db.get_setting(SETTING_WAIT_FOLDER)
    rtm_import_email = db.get_setting(SETTING_RTM_IMPORT_EMAIL)
    assert wait_folder is not None
    assert rtm_import_email is not None

    contact = db.get_contact(delegate_name)
    if not contact:
        return ERR_CONTACT_NOT_FOUND.format(name=delegate_name)
    contact_list_tag = contact.rtm_list_tag
    if not contact_list_tag:
        return ERR_CONTACT_NO_RTM_TAG.format(name=contact.name, email=contact.email)

    email_data = email_service.show_email(email_id, folder)
    email_subject = ""
    email_from = ""
    email_body = ""
    try:
        parsed = json.loads(email_data)
        email_subject = parsed.get("subject", "")
        email_from = parsed.get("from", "")
        email_body = parsed.get("body", "")
    except (json.JSONDecodeError, TypeError):
        pass

    effective_topic = topic or email_subject
    effective_priority = priority or _get_setting_or_default(
        db, SETTING_DEFAULT_PRIORITY, DEFAULT_PRIORITY
    )
    effective_due = due or _get_setting_or_default(db, SETTING_DEFAULT_DUE, DEFAULT_DUE)

    rtm_tag = ""
    project_name = None
    if project:
        proj_svc = ProjectService(db)
        proj = proj_svc.find_project(project)
        if proj and proj.rtm_tag:
            rtm_tag = proj.rtm_tag
            project_name = proj.name

    if not rtm_tag:
        default_tag = db.get_setting(SETTING_RTM_DEFAULT_TAG)
        if default_tag:
            rtm_tag = default_tag

    tracking_svc = TrackingService(db)
    tracking_id = tracking_svc.create_tracking(
        email_id=email_id,
        email_folder=wait_folder,
        email_subject=email_subject,
        email_from=email_from,
        task_name=effective_topic,
        delegated_to=contact.name,
        project_name=project_name,
    )

    delegation_svc = DelegationService()
    subject = delegation_svc.build_delegation_subject(
        topic=effective_topic,
        priority=effective_priority,
        due=effective_due,
        rtm_tag=rtm_tag,
        contact_list_tag=contact_list_tag,
    )
    body = delegation_svc.build_delegation_body(email_body, tracking_id)

    draft_result = email_service.draft_compose(
        to_addresses=[contact.email],
        subject=subject,
        body=body,
        bcc_addresses=[rtm_import_email],
    )

    move_result = email_service.move_email(email_id, wait_folder, source_folder=folder)

    return (
        f"Delegation draft created for {contact.name} ({contact.email}).\n"
        f"Subject: {subject}\n"
        f"Draft: {draft_result}\n"
        f"Email moved to {wait_folder}: {move_result}\n"
        f"Tracking ID: {tracking_id}"
    )


def pm_check_delegation_reply(
    ctx: RunContext[Deps],
    email_id: str,
    folder: str = "INBOX",
) -> str:
    """Check if an incoming email is a reply to a delegated task.

    Extracts [PM-TRACK:<uuid>] from the email body and looks up the tracking record.
    """
    logger.info(
        "pm_check_delegation_reply: email_id=%r folder=%r", email_id, folder,
    )

    email_service = _get_email_service(ctx)
    if not email_service:
        return ERR_EMAIL_NOT_LOADED

    db = _get_db(ctx)

    email_data = email_service.show_email(email_id, folder)
    email_body = ""
    try:
        parsed = json.loads(email_data)
        email_body = parsed.get("body", "")
    except (json.JSONDecodeError, TypeError):
        pass

    tracking_svc = TrackingService(db)
    tracking_id = tracking_svc.extract_tracking_id(email_body)

    if not tracking_id:
        return "No tracking ID found in this email. It is not a delegation reply."

    record = tracking_svc.find_by_tracking_id(tracking_id)
    if not record:
        return f"Tracking ID {tracking_id} found but no matching record exists."

    return (
        f"This is a delegation reply!\n\n"
        f"Original delegation:\n"
        f"  Task: {record.task_name}\n"
        f"  Delegated to: {record.delegated_to}\n"
        f"  Original email subject: {record.email_subject}\n"
        f"  Original email from: {record.email_from}\n"
        f"  Tracking ID: {record.tracking_id}\n\n"
        f"What would you like to do?\n"
        f"- reply_and_archive: Reply to original sender and archive\n"
        f"- archive: Just archive both emails\n"
        f"- leave: Leave everything as is"
    )


def pm_resolve_delegation(
    ctx: RunContext[Deps],
    tracking_id: str,
    action: str,
    reply_body: str = "",
) -> str:
    """Handle a completed delegation.

    Actions: 'reply_and_archive', 'archive', 'leave'.
    """
    logger.info(
        "pm_resolve_delegation: tracking_id=%r action=%r", tracking_id, action,
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
        results.append(f"Reply drafted to original sender: {reply_result}")

    if action in (ACTION_ARCHIVE, ACTION_REPLY_AND_ARCHIVE):
        done_result = email_service.mark_as_done(
            email_id=record.email_id,
            database=ctx.deps.plugin_data.get("database"),
            folder=record.email_folder,
        )
        results.append(f"Original email archived: {done_result}")

    if action == ACTION_LEAVE:
        results.append("Emails left in current folders.")

    tracking_svc.complete_tracking(tracking_id)
    results.append("Delegation tracking marked as completed.")

    return "\n".join(results)


def pm_set_contact(
    ctx: RunContext[Deps],
    name: str,
    email: str,
    rtm_list_tag: str = "",
) -> str:
    """Store or update a delegation contact with optional RTM list tag.

    The rtm_list_tag should be the RTM Smart Add list tag (e.g., '#XIDA - Markus').
    """
    logger.info("pm_set_contact: name=%r email=%r", name, email)
    db = _get_db(ctx)
    contact = db.set_contact(
        name=name,
        email=email,
        rtm_list_tag=rtm_list_tag or None,
    )
    tag_info = f", RTM list tag: {contact.rtm_list_tag}" if contact.rtm_list_tag else ""
    return f"Contact '{contact.name}' set ({contact.email}{tag_info})."


def pm_list_contacts(ctx: RunContext[Deps]) -> str:
    """List all delegation contacts."""
    logger.info("pm_list_contacts")
    db = _get_db(ctx)
    contacts = db.list_contacts()
    if not contacts:
        return "No contacts configured."
    items = [
        {
            "name": c.name,
            "email": c.email,
            "rtm_list_tag": c.rtm_list_tag or "",
        }
        for c in contacts
    ]
    return json.dumps({"contacts": items})
