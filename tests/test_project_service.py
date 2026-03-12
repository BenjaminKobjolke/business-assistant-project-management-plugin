"""Tests for ProjectService."""

from __future__ import annotations

import json

from business_assistant_pm.database import PmDatabase
from business_assistant_pm.project_service import ProjectService


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

    def test_list_projects(self, db: PmDatabase) -> None:
        svc = ProjectService(db)
        svc.add_project("A", rtm_tag="#a")
        svc.add_project("B")
        result = svc.list_projects()
        data = json.loads(result)
        assert len(data["projects"]) == 2
        assert data["projects"][0]["name"] == "A"
        assert data["projects"][0]["rtm_tag"] == "#a"


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
        )
        db.add_synonym(project.id, "f")
        result = svc.format_project_details(project)
        assert "RTM Tag: #full" in result
        assert "Obsidian: vault/notes/full.md" in result
        assert "Synonyms: f" in result
