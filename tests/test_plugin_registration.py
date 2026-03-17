"""Tests for PM plugin registration."""

from __future__ import annotations

from unittest.mock import patch

from business_assistant.plugins.registry import PluginRegistry

from business_assistant_pm.plugin import register


class TestPluginRegistration:
    @patch("business_assistant_pm.plugin.PmDatabase")
    def test_register_creates_tools(self, mock_db_cls, monkeypatch) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)

        assert len(registry.all_tools()) == 30
        assert len(registry.plugins) == 1
        assert registry.plugins[0].name == "project_management"
        assert registry.plugins[0].category == "project_management"

    @patch("business_assistant_pm.plugin.PmDatabase")
    def test_register_required_categories(self, mock_db_cls, monkeypatch) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)

        plugin_info = registry.plugins[0]
        assert "todo" in plugin_info.required_categories
        assert "email" in plugin_info.required_categories
        assert "notes" in plugin_info.required_categories
        assert "calendar" in plugin_info.required_categories
        assert "filesystem" in plugin_info.required_categories
        assert "timetracking" in plugin_info.required_categories

    @patch("business_assistant_pm.plugin.PmDatabase")
    def test_register_system_prompt(self, mock_db_cls, monkeypatch) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)

        prompt = registry.system_prompt_extras()
        assert "pm_create_todo_from_email" in prompt
        assert "pm_delegate_email" in prompt

    @patch("business_assistant_pm.plugin.PmDatabase")
    def test_register_stores_database_in_plugin_data(
        self, mock_db_cls, monkeypatch,
    ) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)

        assert "pm_database" in registry.plugin_data

    @patch("business_assistant_pm.plugin.PmDatabase")
    def test_tool_names(self, mock_db_cls, monkeypatch) -> None:
        monkeypatch.delenv("PM_DB_PATH", raising=False)
        registry = PluginRegistry()
        register(registry)

        tool_names = {t.name for t in registry.all_tools()}
        expected = {
            "pm_create_todo_from_email",
            "pm_complete_tracked_task",
            "pm_handle_completed_email",
            "pm_delegate_email",
            "pm_check_delegation_reply",
            "pm_resolve_delegation",
            "pm_contacts",
            "pm_list_projects",
            "pm_create_project",
            "pm_create_project_from_note",
            "pm_add_project",
            "pm_match_project",
            "pm_sync_project_from_obsidian",
            "pm_store_file_in_project",
            "pm_settings",
            "pm_tracking",
            "pm_manage_workflow",
            "pm_run_workflow",
            "pm_check_synonym_conflicts",
            "pm_manage_match_info",
            "pm_match_email_to_project",
            "pm_update_project",
            "pm_log_time",
            "pm_list_timetracking_projects",
            "pm_link_email_to_project",
            "pm_list_email_references",
            "pm_add_project_update",
            "pm_set_deadlines_list",
            "pm_get_deadlines",
            "pm_add_deadline",
        }
        assert tool_names == expected
