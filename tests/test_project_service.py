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


class TestPmUpdateProjectSynonyms:
    def test_add_and_remove_synonyms(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        db.add_project("Project")
        result = pm_update_project(ctx, "Project", add_synonyms="alias1, alias2")
        assert "added" in result
        result = pm_update_project(ctx, "Project", remove_synonyms="alias1")
        assert "removed" in result

    def test_remove_synonym_not_found(self, db: PmDatabase) -> None:
        ctx = _make_ctx(db)
        db.add_project("Project")
        result = pm_update_project(ctx, "Project", remove_synonyms="ghost")
        assert "not found" in result


class TestUpdateObsidianField:
    def test_updates_existing_rtm_tag(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", rtm_tag="#old", obsidian_vault="vault", obsidian_path="test.md",
        )
        content = "**RTM Tag**\n\n#old_tag\n\n**Projektordner**\nOldFolder\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new_tag")

        assert result == "Obsidian note updated."
        obsidian.edit_note.assert_called_once()
        written_content = obsidian.edit_note.call_args[0][2]
        assert "#new_tag" in written_content
        assert "#old_tag" not in written_content

    def test_updates_existing_projektordner(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="test.md",
        )
        content = "**RTM Tag**\n\n#p_test\n\n**Projektordner**\nOldFolder\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "Projektordner", "NewFolder")

        assert result == "Obsidian note updated."
        written_content = obsidian.edit_note.call_args[0][2]
        assert "NewFolder" in written_content
        assert "OldFolder" not in written_content

    def test_field_not_in_note_returns_none(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="test.md",
        )
        content = "Just plain text without any headings.\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new")

        assert result is None
        obsidian.edit_note.assert_not_called()

    def test_no_vault_returns_none(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        obsidian = MagicMock()
        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new")
        assert result is None
        obsidian.read_note.assert_not_called()

    def test_read_failure_returns_none(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="test.md",
        )
        obsidian = MagicMock()
        obsidian.read_note.side_effect = RuntimeError("connection failed")

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new")

        assert result is None

    def test_write_failure_returns_none(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="test.md",
        )
        content = "**RTM Tag**\n\n#old_tag\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})
        obsidian.edit_note.side_effect = RuntimeError("write failed")

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new")

        assert result is None

    def test_rtm_tag_with_escaped_hash(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="test.md",
        )
        content = "**RTM Tag**\n\n\\#old_tag\n\n**Next**\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        svc = ProjectService(db)
        result = svc.update_obsidian_field(project, obsidian, "RTM Tag", "#new_tag")

        assert result == "Obsidian note updated."
        written_content = obsidian.edit_note.call_args[0][2]
        assert "#new_tag" in written_content
        assert "\\#old_tag" not in written_content


def _make_ctx_with_obsidian(
    db: PmDatabase, obsidian_service: MagicMock,
) -> RunContext[Deps]:
    """Build a RunContext with both PM database and obsidian service."""
    plugin_data: dict = {
        PLUGIN_DATA_PM_DATABASE: db,
        "obsidian_service": obsidian_service,
    }
    deps = MagicMock(spec=Deps)
    deps.plugin_data = plugin_data
    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx


class TestFormatUpdateLines:
    def test_single_line(self) -> None:
        result = ProjectService._format_update_lines("hello world")
        assert result == ["hello world"]

    def test_multiline(self) -> None:
        result = ProjectService._format_update_lines("line1\nline2\nline3")
        assert result == ["line1", "line2", "line3"]

    def test_empty_lines_skipped(self) -> None:
        result = ProjectService._format_update_lines("line1\n\n\nline2")
        assert result == ["line1", "line2"]

    def test_whitespace_stripped(self) -> None:
        result = ProjectService._format_update_lines("  padded  \n  also  ")
        assert result == ["padded", "also"]

    def test_empty_content(self) -> None:
        result = ProjectService._format_update_lines("")
        assert result == []


class TestInsertUpdateIntoSection:
    def test_section_exists_new_date(self) -> None:
        note = "# Title\n\n## Project Updates\n2026-03-16\nOld entry\n"
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["New entry"],
        )
        assert "2026-03-17" in result
        assert "New entry" in result
        assert "Old entry" in result

    def test_section_exists_existing_date(self) -> None:
        note = "# Title\n\n## Project Updates\n2026-03-17\nExisting entry\n"
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["Added entry"],
        )
        assert result.count("2026-03-17") == 1
        assert "Existing entry" in result
        assert "Added entry" in result
        # Added entry should come after existing
        assert result.index("Existing entry") < result.index("Added entry")

    def test_section_missing_creates_section(self) -> None:
        note = "# Title\n\nSome content\n"
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["First update"],
        )
        assert "## Project Updates" in result
        assert "2026-03-17" in result
        assert "First update" in result

    def test_multiple_dates_appends_to_correct_one(self) -> None:
        note = (
            "## Project Updates\n"
            "2026-03-16\nOld entry\n"
            "2026-03-17\nToday entry\n"
        )
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["New today"],
        )
        assert result.count("2026-03-17") == 1
        assert "New today" in result
        assert "Old entry" in result

    def test_section_followed_by_another_heading(self) -> None:
        note = (
            "## Project Updates\n"
            "2026-03-16\nEntry\n\n"
            "## Other Section\nOther content\n"
        )
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["New update"],
        )
        assert "New update" in result
        assert "## Other Section" in result
        # New update should be before the other section
        assert result.index("New update") < result.index("## Other Section")

    def test_content_with_urls(self) -> None:
        note = "## Project Updates\n"
        result = ProjectService._insert_update_into_section(
            note, "2026-03-17", ["Vimeo: https://vimeo.com/123"],
        )
        assert "https://vimeo.com/123" in result

    def test_empty_lines_no_change(self) -> None:
        note = "# Title\n"
        result = ProjectService._insert_update_into_section(note, "2026-03-17", [])
        assert result == note

    def test_existing_date_between_two_dates(self) -> None:
        note = (
            "## Project Updates\n"
            "2026-03-15\nOldest\n"
            "2026-03-16\nMiddle\n"
            "2026-03-17\nToday\n"
        )
        result = ProjectService._insert_update_into_section(
            note, "2026-03-16", ["Added to middle"],
        )
        assert "Added to middle" in result
        # Should not duplicate the date
        assert result.count("2026-03-16") == 1
        # Should appear after "Middle" but before "2026-03-17"
        assert result.index("Middle") < result.index("Added to middle")
        assert result.index("Added to middle") < result.index("2026-03-17\n")


class TestCopyFileToResources:
    def test_happy_path(self, tmp_path) -> None:
        # Create source file
        src = tmp_path / "source" / "image.png"
        src.parent.mkdir()
        src.write_bytes(b"fake image data")

        # Create vault directory
        vault = tmp_path / "vault"
        vault.mkdir()

        svc = ProjectService.__new__(ProjectService)
        vault_rel, filename = svc.copy_file_to_resources(
            str(vault), "Projects/2026/MyProject.md", str(src),
        )

        assert filename == "image.png"
        assert vault_rel == "Projects/2026/_resources/image.png"
        assert (vault / "Projects" / "2026" / "_resources" / "image.png").is_file()

    def test_root_level_note(self, tmp_path) -> None:
        src = tmp_path / "file.pdf"
        src.write_bytes(b"pdf")
        vault = tmp_path / "vault"
        vault.mkdir()

        svc = ProjectService.__new__(ProjectService)
        vault_rel, filename = svc.copy_file_to_resources(
            str(vault), "note.md", str(src),
        )
        assert vault_rel == "_resources/file.pdf"
        assert (vault / "_resources" / "file.pdf").is_file()


class TestAppendProjectUpdate:
    def test_happy_path(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="p.md",
        )
        note_content = "# Title\n\n## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        svc = ProjectService(db)
        result = svc.append_project_update(
            project, obsidian, "Link: https://example.com", "2026-03-17",
        )

        assert "added" in result
        assert "2026-03-17" in result
        obsidian.edit_note.assert_called_once()
        written = obsidian.edit_note.call_args[0][2]
        assert "https://example.com" in written
        assert "2026-03-17" in written

    def test_with_file_entries(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="p.md",
        )
        note_content = "## Project Updates\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": note_content})

        svc = ProjectService(db)
        result = svc.append_project_update(
            project, obsidian, "", "2026-03-17",
            file_entries=["Projects/_resources/img.png"],
        )

        assert "added" in result
        written = obsidian.edit_note.call_args[0][2]
        assert "![[Projects/_resources/img.png]]" in written

    def test_no_vault_returns_none(self, db: PmDatabase) -> None:
        project = db.add_project("Test")
        obsidian = MagicMock()
        svc = ProjectService(db)
        result = svc.append_project_update(project, obsidian, "text", "2026-03-17")
        assert result is None

    def test_no_content_no_files(self, db: PmDatabase) -> None:
        project = db.add_project(
            "Test", obsidian_vault="vault", obsidian_path="p.md",
        )
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": "note"})

        svc = ProjectService(db)
        result = svc.append_project_update(project, obsidian, "", "2026-03-17")
        assert "No content" in result


class TestPmUpdateProjectObsidianPush:
    def test_rtm_tag_update_pushes_to_obsidian(self, db: PmDatabase) -> None:
        db.add_project(
            "MyProject", obsidian_vault="vault", obsidian_path="p.md",
        )
        content = "**RTM Tag**\n\n#old\n\n**Projektordner**\nOld\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        ctx = _make_ctx_with_obsidian(db, obsidian)
        result = pm_update_project(ctx, "MyProject", rtm_tag="#new_tag")

        assert "updated" in result
        obsidian.edit_note.assert_called_once()
        written_content = obsidian.edit_note.call_args[0][2]
        assert "#new_tag" in written_content

    def test_no_obsidian_link_skips_push(self, db: PmDatabase) -> None:
        db.add_project("MyProject")
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "MyProject", rtm_tag="#new_tag")
        assert "updated" in result

    def test_no_obsidian_service_skips_push(self, db: PmDatabase) -> None:
        db.add_project(
            "MyProject", obsidian_vault="vault", obsidian_path="p.md",
        )
        ctx = _make_ctx(db)
        result = pm_update_project(ctx, "MyProject", rtm_tag="#new_tag")
        assert "updated" in result

    def test_project_folder_update_pushes_to_obsidian(self, db: PmDatabase) -> None:
        db.add_project(
            "MyProject", obsidian_vault="vault", obsidian_path="p.md",
        )
        content = "**Projektordner**\nOldFolder\n"
        obsidian = MagicMock()
        obsidian.read_note.return_value = json.dumps({"content": content})

        ctx = _make_ctx_with_obsidian(db, obsidian)
        result = pm_update_project(ctx, "MyProject", project_folder="NewFolder")

        assert "updated" in result
        obsidian.edit_note.assert_called()
        written_content = obsidian.edit_note.call_args[0][2]
        assert "NewFolder" in written_content
