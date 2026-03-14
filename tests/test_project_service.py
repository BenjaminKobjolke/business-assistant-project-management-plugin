"""Tests for ProjectService and project synonym tools."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from business_assistant_pm.constants import PLUGIN_DATA_PM_DATABASE
from business_assistant_pm.database import PmDatabase
from business_assistant_pm.project_service import ProjectService
from business_assistant_pm.tools_project import (
    pm_add_project_synonym,
    pm_remove_project_synonym,
    pm_update_project,
)


class TestProjectService:
    def test_add_project(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        result = svc.add_project("Test Project", rtm_tag="#test")
        assert "created" in result

    def test_add_duplicate_project(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Unique")
        result = svc.add_project("Unique")
        assert "Error" in result

    def test_find_project_by_name(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("FindMe")
        project = svc.find_project("FindMe")
        assert project is not None
        assert project.name == "FindMe"

    def test_find_project_by_synonym(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Full Name")
        svc.add_synonym("Full Name", "alias")
        project = svc.find_project("alias")
        assert project is not None
        assert project.name == "Full Name"

    def test_find_project_not_found(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        assert svc.find_project("nope") is None

    def test_add_synonym(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Project")
        result = svc.add_synonym("Project", "shortname")
        assert "added" in result

    def test_add_synonym_project_not_found(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        result = svc.add_synonym("Ghost", "alias")
        assert "not found" in result

    def test_add_synonym_duplicate_same_project(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Project")
        svc.add_synonym("Project", "alias")
        result = svc.add_synonym("Project", "alias")
        assert "already exists" in result
        assert "Project" in result

    def test_add_synonym_duplicate_other_project(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Alpha")
        svc.add_project("Beta")
        svc.add_synonym("Alpha", "shared")
        result = svc.add_synonym("Beta", "shared")
        assert "ERROR" in result
        assert "Alpha" in result

    def test_add_synonym_conflicts_with_project_name(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Alpha")
        svc.add_project("Beta")
        result = svc.add_synonym("Alpha", "Beta")
        assert "ERROR" in result
        assert "conflicts" in result

    def test_remove_synonym(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Project")
        svc.add_synonym("Project", "removable")
        result = svc.remove_synonym("removable")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        result = svc.remove_synonym("ghost")
        assert "not found" in result

    def test_add_synonym_case_insensitive_duplicate(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Project")
        svc.add_synonym("Project", "alias")
        result = svc.add_synonym("Project", "ALIAS")
        assert "already exists" in result

    def test_check_synonym_conflicts_none(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Alpha")
        svc.add_synonym("Alpha", "a1")
        result = json.loads(svc.check_synonym_conflicts())
        assert result["status"] == "ok"

    def test_check_synonym_conflicts_found(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Alpha")
        p2 = db.add_project("Beta")
        # Directly add synonym via db to bypass service-level checks
        db.add_synonym(p2.id, "alpha")
        result = json.loads(svc.check_synonym_conflicts())
        assert result["status"] == "conflicts_found"
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["synonym"] == "alpha"
        assert result["conflicts"][0]["owned_by"] == "Beta"
        assert result["conflicts"][0]["conflicts_with"] == "Alpha"

    def test_list_projects(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("A", rtm_tag="#a")
        svc.add_project("B")
        result = svc.list_projects()
        data = json.loads(result)
        assert len(data["projects"]) == 2
        assert data["projects"][0]["name"] == "A"
        assert data["projects"][0]["rtm_tag"] == "#a"

    def test_list_projects_includes_folder(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("FolderP", project_folder="MyFolder")
        result = svc.list_projects()
        data = json.loads(result)
        assert data["projects"][0]["project_folder"] == "MyFolder"

    def test_list_projects_includes_timetracking_project_id(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("TTP", timetracking_project_id="tt-99")
        result = svc.list_projects()
        data = json.loads(result)
        assert data["projects"][0]["timetracking_project_id"] == "tt-99"

    def test_add_project_with_folder(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        result = svc.add_project("WithFolder", project_folder="Folder123")
        assert "created" in result
        project = svc.find_project("WithFolder")
        assert project is not None
        assert project.project_folder == "Folder123"


class TestSyncFromObsidianMatchRules:
    def test_sync_parses_match_rules(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Test", obsidian_vault="vault", obsidian_path="test.md")

        content = (
            "**RTM Tag**\n\n#p_test\n\n"
            "**Matching**\n"
            "email_domains: test.com\n"
            "keywords: widget\n"
        )
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        result = svc.sync_from_obsidian("Test", obsidian, "vault", "test.md")
        assert "Match rules: 2" in result

        project = db.get_project_by_name("Test")
        assert project is not None
        rules = db.get_match_rules_for_project(project.id)
        assert len(rules) == 2

    def test_sync_replaces_existing_rules(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("Test", obsidian_vault="vault", obsidian_path="test.md")
        project = db.get_project_by_name("Test")
        assert project is not None

        # Add pre-existing rules
        db.add_match_rule(project.id, "email_domain", "old.com")
        db.add_match_rule(project.id, "keyword", "oldword")

        content = (
            "**RTM Tag**\n\n#p_test\n\n"
            "**Matching**\n"
            "email_domains: new.com\n"
        )
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        svc.sync_from_obsidian("Test", obsidian, "vault", "test.md")

        rules = db.get_match_rules_for_project(project.id)
        assert len(rules) == 1
        assert rules[0].value == "new.com"


class TestExtractField:
    def test_extract_kundenprojektname(self) -> None:
        content = "# Project\n\n**Kundenprojektname**\n\nACME Corp\n\n**RTM Tag**\n"
        result = ProjectService.extract_field(content, "Kundenprojektname")
        assert result == "ACME Corp"

    def test_extract_projektordner(self) -> None:
        content = "**Projektordner**\n\nACME_Folder\n\nMore text"
        result = ProjectService.extract_field(content, "Projektordner")
        assert result == "ACME_Folder"

    def test_extract_without_blank_line(self) -> None:
        content = "**Kundenprojektname**\nDirect Value\n"
        result = ProjectService.extract_field(content, "Kundenprojektname")
        assert result == "Direct Value"

    def test_extract_field_not_found(self) -> None:
        content = "No relevant headings here"
        assert ProjectService.extract_field(content, "Kundenprojektname") is None

    def test_extract_empty_value(self) -> None:
        content = "**Kundenprojektname**\n\n\n**Next Section**\n"
        assert ProjectService.extract_field(content, "Kundenprojektname") is None

    def test_extract_strips_whitespace(self) -> None:
        content = "**Kundenprojektname**\n\n  Spaced Value  \n"
        result = ProjectService.extract_field(content, "Kundenprojektname")
        assert result == "Spaced Value"


class TestSuggestSynonyms:
    def test_all_sources(self) -> None:
        content = (
            "**Kundenprojektname**\n\nACME Corp\n\n"
            "**Projektordner**\n\nACME_Folder\n"
        )
        result = ProjectService.suggest_synonyms(content, "projects/2026/my_project.md")
        assert result == ["ACME Corp", "ACME_Folder", "my_project"]

    def test_deduplicates_case_insensitive(self) -> None:
        content = (
            "**Kundenprojektname**\n\nmy_project\n\n"
            "**Projektordner**\n\nOther\n"
        )
        result = ProjectService.suggest_synonyms(content, "folder/my_project.md")
        # "my_project" from Kundenprojektname and filename — first occurrence kept
        assert result == ["my_project", "Other"]

    def test_no_fields_only_filename(self) -> None:
        content = "Just some plain text"
        result = ProjectService.suggest_synonyms(content, "notes/hello_world.md")
        assert result == ["hello_world"]

    def test_no_md_extension(self) -> None:
        content = "Plain text"
        result = ProjectService.suggest_synonyms(content, "notes/plain_file")
        assert result == ["plain_file"]

    def test_filename_without_path(self) -> None:
        content = "Plain text"
        result = ProjectService.suggest_synonyms(content, "simple.md")
        assert result == ["simple"]


class TestExtractRtmTag:
    def test_extract_with_blank_line(self) -> None:
        content = "Some text\n\n**RTM Tag**\n\n#p_my_project\n\nMore text"
        tag = ProjectService.extract_rtm_tag(content)
        assert tag == "#p_my_project"

    def test_extract_without_blank_line(self) -> None:
        content = "Some text\n**RTM Tag**\n#p_direct\nMore text"
        tag = ProjectService.extract_rtm_tag(content)
        assert tag == "#p_direct"

    def test_extract_with_underscores_and_numbers(self) -> None:
        content = "**RTM Tag**\n\n#p_l-b_2026"
        tag = ProjectService.extract_rtm_tag(content)
        assert tag == "#p_l-b_2026"

    def test_extract_no_tag(self) -> None:
        content = "Just some text without RTM Tag section"
        assert ProjectService.extract_rtm_tag(content) is None

    def test_extract_with_escaped_hash(self) -> None:
        content = "Some text\n\n**RTM Tag**\n\n\\#p_fahrradschreiber\n\nMore text"
        tag = ProjectService.extract_rtm_tag(content)
        assert tag == "#p_fahrradschreiber"

    def test_extract_malformed(self) -> None:
        content = "**RTM Tag**\n\nno hash here"
        assert ProjectService.extract_rtm_tag(content) is None


class TestFormatProjectDetails:
    def test_format_basic(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        project = db.add_project("Test")
        result = svc.format_project_details(project)
        assert "Project: Test" in result

    def test_format_with_all_fields(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        project = db.add_project(
            "Full",
            rtm_tag="#full",
            obsidian_vault="vault",
            obsidian_path="notes/full.md",
            project_folder="FullFolder",
        )
        db.add_synonym(project.id, "f")
        result = svc.format_project_details(project)
        assert "RTM Tag: #full" in result
        assert "Obsidian: vault/notes/full.md" in result
        assert "Project Folder: FullFolder" in result
        assert "Synonyms: f" in result

    def test_format_with_timetracking(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        project = db.add_project("TTProject", timetracking_project_id="tt-42")
        result = svc.format_project_details(project)
        assert "Timetracking Project ID: tt-42" in result


def _make_ctx(db: PmDatabase) -> RunContext[Deps]:
    """Build a minimal RunContext with plugin_data."""
    plugin_data: dict = {PLUGIN_DATA_PM_DATABASE: db}
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestPmUpdateProject:
    def test_update_project_folder(self, db: PmDatabase) -> None:
        db.add_project("MyProject")
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "MyProject", project_folder="NewFolder")
        assert "updated" in result
        assert "project_folder='NewFolder'" in result
        project = db.get_project_by_name("MyProject")
        assert project is not None
        assert project.project_folder == "NewFolder"

    def test_update_rtm_tag(self, db: PmDatabase) -> None:
        db.add_project("MyProject")
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "MyProject", rtm_tag="#new_tag")
        assert "updated" in result
        project = db.get_project_by_name("MyProject")
        assert project is not None
        assert project.rtm_tag == "#new_tag"

    def test_update_project_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "Ghost", project_folder="X")
        assert "not found" in result

    def test_update_no_fields(self, db: PmDatabase) -> None:
        db.add_project("MyProject")
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "MyProject")
        assert "No fields to update" in result

    def test_update_multiple_fields(self, db: PmDatabase) -> None:
        db.add_project("MyProject")
        ctx = _make_ctx(db)
        result = pm_update_project(
            ctx, "MyProject", rtm_tag="#tag", project_folder="Folder",
        )
        assert "updated" in result
        project = db.get_project_by_name("MyProject")
        assert project is not None
        assert project.rtm_tag == "#tag"
        assert project.project_folder == "Folder"


class TestPmRemoveProjectSynonym:
    def test_remove_synonym(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        db.add_project("Project")
        pm_add_project_synonym(ctx, "Project", "removable")
        result = pm_remove_project_synonym(ctx, "removable")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        result = pm_remove_project_synonym(ctx, "ghost")
        assert "not found" in result
