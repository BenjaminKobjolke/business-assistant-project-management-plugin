"""Plugin registration — defines PydanticAI tools for project management."""

from __future__ import annotations

import logging

from business_assistant.plugins.registry import PluginInfo, PluginRegistry
from pydantic_ai import Tool

from .config import load_pm_settings
from .constants import (
    PLUGIN_CATEGORY,
    PLUGIN_DATA_PM_DATABASE,
    PLUGIN_DESCRIPTION,
    PLUGIN_NAME,
    REQUIRED_CATEGORIES,
    SYSTEM_PROMPT_PM,
)
from .database import PmDatabase
from .tools_delegation import (
    pm_check_delegation_reply,
    pm_contacts,
    pm_delegate_email,
    pm_resolve_delegation,
)
from .tools_project import (
    pm_add_project,
    pm_check_synonym_conflicts,
    pm_create_project,
    pm_create_project_from_note,
    pm_list_projects,
    pm_list_timetracking_projects,
    pm_log_time,
    pm_manage_match_info,
    pm_match_email_to_project,
    pm_match_project,
    pm_store_file_in_project,
    pm_sync_project_from_obsidian,
    pm_update_project,
)
from .tools_settings import (
    pm_settings,
    pm_tracking,
)
from .tools_tracking import (
    pm_complete_tracked_task,
    pm_create_todo_from_email,
    pm_handle_completed_email,
    pm_link_email_to_project,
    pm_list_email_references,
)
from .tools_workflow import (
    pm_manage_workflow,
    pm_run_workflow,
)

logger = logging.getLogger(__name__)


def register(registry: PluginRegistry) -> None:
    """Register the project management plugin."""
    from business_assistant.config.log_setup import add_plugin_logging

    add_plugin_logging("pm", "business_assistant_pm")

    settings = load_pm_settings()
    db = PmDatabase(settings.db_path)

    tools = [
        Tool(pm_create_todo_from_email, name="pm_create_todo_from_email"),
        Tool(pm_complete_tracked_task, name="pm_complete_tracked_task"),
        Tool(pm_handle_completed_email, name="pm_handle_completed_email"),
        Tool(pm_link_email_to_project, name="pm_link_email_to_project"),
        Tool(pm_list_email_references, name="pm_list_email_references"),
        Tool(pm_delegate_email, name="pm_delegate_email"),
        Tool(pm_check_delegation_reply, name="pm_check_delegation_reply"),
        Tool(pm_resolve_delegation, name="pm_resolve_delegation"),
        Tool(pm_contacts, name="pm_contacts"),
        Tool(pm_list_projects, name="pm_list_projects"),
        Tool(pm_create_project, name="pm_create_project"),
        Tool(pm_create_project_from_note, name="pm_create_project_from_note"),
        Tool(pm_add_project, name="pm_add_project"),
        Tool(pm_update_project, name="pm_update_project"),
        Tool(pm_match_project, name="pm_match_project"),
        Tool(pm_sync_project_from_obsidian, name="pm_sync_project_from_obsidian"),
        Tool(pm_store_file_in_project, name="pm_store_file_in_project"),
        Tool(pm_check_synonym_conflicts, name="pm_check_synonym_conflicts"),
        Tool(pm_manage_match_info, name="pm_manage_match_info"),
        Tool(pm_match_email_to_project, name="pm_match_email_to_project"),
        Tool(pm_log_time, name="pm_log_time"),
        Tool(pm_list_timetracking_projects, name="pm_list_timetracking_projects"),
        Tool(pm_settings, name="pm_settings"),
        Tool(pm_tracking, name="pm_tracking"),
        Tool(pm_manage_workflow, name="pm_manage_workflow"),
        Tool(pm_run_workflow, name="pm_run_workflow"),
    ]

    info = PluginInfo(
        name=PLUGIN_NAME,
        description=PLUGIN_DESCRIPTION,
        system_prompt_extra=SYSTEM_PROMPT_PM,
        category=PLUGIN_CATEGORY,
        required_categories=REQUIRED_CATEGORIES,
    )

    registry.register(info, tools)
    registry.plugin_data[PLUGIN_DATA_PM_DATABASE] = db

    logger.info("PM plugin registered with %d tools", len(tools))
