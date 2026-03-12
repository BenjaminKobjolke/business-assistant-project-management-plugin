"""PydanticAI tool functions for project management."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import PurePosixPath

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import (
    ERR_FILESYSTEM_NOT_LOADED,
    ERR_NOTE_CREATION_FAILED,
    ERR_OBSIDIAN_NOT_LOADED,
    ERR_PROJECT_NO_FOLDER,
    ERR_PROJECT_NOT_FOUND,
    ERR_TEMPLATE_READ_FAILED,
    PLUGIN_DATA_PM_DATABASE,
    REQUIRED_SETTINGS_CREATE_PROJECT,
    REQUIRED_SETTINGS_FROM_NOTE,
    SETTING_PROJECT_FILES_BASE_PATH,
    SETTING_PROJECT_FOLDER_PATH,
    SETTING_PROJECT_TEMPLATE_PATH,
    SETTING_PROJECT_VAULT,
)
from .database import PmDatabase
from .plugin_helpers import _get_filesystem_service, _get_obsidian_service, _require_setting
from .project_service import ProjectService

logger = logging.getLogger(__name__)


def _get_db(ctx: RunContext[Deps]) -> PmDatabase:
    return ctx.deps.plugin_data[PLUGIN_DATA_PM_DATABASE]


def pm_list_projects(ctx: RunContext[Deps]) -> str:
    """List all projects with their RTM tags and Obsidian links."""
    logger.info("pm_list_projects")
    db = _get_db(ctx)
    proj_svc = ProjectService(db)
    return proj_svc.list_projects()


def pm_add_project(
    ctx: RunContext[Deps],
    name: str,
    rtm_tag: str = "",
    obsidian_vault: str = "",
    obsidian_path: str = "",
    project_folder: str = "",
) -> str:
    """Create a new project. If vault+path provided, auto-extracts RTM tag from note."""
    logger.info("pm_add_project: name=%r", name)
    db = _get_db(ctx)
    proj_svc = ProjectService(db)

    effective_rtm_tag = rtm_tag or None
    if not rtm_tag and obsidian_vault and obsidian_path:
        obsidian_service = _get_obsidian_service(ctx)
        if obsidian_service:
            try:
                result = obsidian_service.read_note(obsidian_vault, obsidian_path)
                data = json.loads(result)
                content = data.get("content", "")
                extracted = proj_svc.extract_rtm_tag(content)
                if extracted:
                    effective_rtm_tag = extracted
            except Exception:
                pass

    result = proj_svc.add_project(
        name=name,
        rtm_tag=effective_rtm_tag,
        obsidian_vault=obsidian_vault or None,
        obsidian_path=obsidian_path or None,
        project_folder=project_folder or None,
    )

    if project_folder:
        filesystem_service = _get_filesystem_service(ctx)
        if filesystem_service:
            base_path = db.get_setting(SETTING_PROJECT_FILES_BASE_PATH)
            if base_path:
                folder_path_full = f"{base_path}/{project_folder}"
                filesystem_service.create_directory(folder_path_full)

    return result


def pm_add_project_synonym(
    ctx: RunContext[Deps], project_name: str, synonym: str,
) -> str:
    """Add an alternative name for a project (case-insensitive matching)."""
    logger.info("pm_add_project_synonym: project=%r synonym=%r", project_name, synonym)
    db = _get_db(ctx)
    proj_svc = ProjectService(db)
    return proj_svc.add_synonym(project_name, synonym)


def pm_match_project(ctx: RunContext[Deps], reference: str) -> str:
    """Match a reference to a known project by name or synonym."""
    logger.info("pm_match_project: reference=%r", reference)
    db = _get_db(ctx)
    proj_svc = ProjectService(db)
    project = proj_svc.find_project(reference)
    if not project:
        return ERR_PROJECT_NOT_FOUND.format(reference=reference)
    return proj_svc.format_project_details(project)


def pm_sync_project_from_obsidian(
    ctx: RunContext[Deps], project_name: str,
) -> str:
    """Re-read the Obsidian note for a project and update its RTM tag."""
    logger.info("pm_sync_project_from_obsidian: project=%r", project_name)

    obsidian_service = _get_obsidian_service(ctx)
    if not obsidian_service:
        return ERR_OBSIDIAN_NOT_LOADED

    db = _get_db(ctx)
    project = db.get_project_by_name(project_name)
    if not project:
        return ERR_PROJECT_NOT_FOUND.format(reference=project_name)
    vault = project.obsidian_vault
    path = project.obsidian_path
    if not vault or not path:
        return f"Project '{project_name}' has no Obsidian note linked."

    proj_svc = ProjectService(db)
    return proj_svc.sync_from_obsidian(
        project_name, obsidian_service, vault, path,
    )


def pm_create_project(
    ctx: RunContext[Deps],
    filename: str,
    customer_name: str,
    rtm_tag: str,
    project_name: str,
    synonyms: str = "",
    project_folder: str = "",
) -> str:
    """Create a new project from Obsidian template.

    Copies the template note, fills Kundenprojektname and RTM Tag fields,
    creates the note in the year-based project folder, and registers the project.

    Args:
        filename: Name for the MD file (without .md extension).
        customer_name: Value for the Kundenprojektname field.
        rtm_tag: RTM tag (e.g., #p_project_name).
        project_name: Display name for the project in the PM database.
        synonyms: Optional comma-separated alternative names.
        project_folder: Optional Projektordner name for file storage.
    """
    logger.info("pm_create_project: project=%r filename=%r", project_name, filename)

    # 1. Check Obsidian service
    obsidian_service = _get_obsidian_service(ctx)
    if not obsidian_service:
        return ERR_OBSIDIAN_NOT_LOADED

    # 2. Check required settings
    db = _get_db(ctx)
    for key in REQUIRED_SETTINGS_CREATE_PROJECT:
        err = _require_setting(db, key)
        if err:
            return err

    vault = db.get_setting(SETTING_PROJECT_VAULT)
    template_path = db.get_setting(SETTING_PROJECT_TEMPLATE_PATH)
    folder_path = db.get_setting(SETTING_PROJECT_FOLDER_PATH)
    assert vault is not None
    assert template_path is not None
    assert folder_path is not None

    # 3. Read template
    try:
        raw = obsidian_service.read_note(vault, template_path)
        data = json.loads(raw)
        template_content = data.get("content", "")
    except Exception as e:
        return ERR_TEMPLATE_READ_FAILED.format(error=e)

    # 4. Fill template fields
    proj_svc = ProjectService(db)
    filled_content = proj_svc.fill_template_fields(
        template_content, customer_name, rtm_tag, project_folder or None,
    )

    # 5. Build target path
    target_path = proj_svc.build_project_note_path(folder_path, filename)

    # 6. Create note in Obsidian
    try:
        obsidian_service.create_note(vault, target_path, filled_content)
    except Exception as e:
        return ERR_NOTE_CREATION_FAILED.format(error=e)

    # 7. Register project in database
    result = proj_svc.add_project(
        name=project_name,
        rtm_tag=rtm_tag,
        obsidian_vault=vault,
        obsidian_path=target_path,
        project_folder=project_folder or None,
    )

    # 8. Create project folder on disk if project_folder provided
    folder_created = ""
    if project_folder:
        filesystem_service = _get_filesystem_service(ctx)
        if not filesystem_service:
            return ERR_FILESYSTEM_NOT_LOADED
        err = _require_setting(db, SETTING_PROJECT_FILES_BASE_PATH)
        if err:
            return err
        base_path = db.get_setting(SETTING_PROJECT_FILES_BASE_PATH)
        assert base_path is not None
        folder_path_full = f"{base_path}/{project_folder}"
        dir_result = filesystem_service.create_directory(folder_path_full)
        if not dir_result.startswith("{"):
            return dir_result
        folder_created = f"Folder created: {folder_path_full}"

    # 9. Add synonyms if provided
    synonym_results = []
    if synonyms:
        for synonym in (s.strip() for s in synonyms.split(",") if s.strip()):
            synonym_results.append(proj_svc.add_synonym(project_name, synonym))

    parts = [result, f"Note created at: {vault}/{target_path}"]
    if folder_created:
        parts.append(folder_created)
    parts.extend(synonym_results)
    return "\n".join(parts)


def pm_create_project_from_note(
    ctx: RunContext[Deps],
    note_path: str,
    project_name: str,
) -> str:
    """Create a project from an existing Obsidian note.

    Reads the note, extracts the RTM tag, and suggests synonyms based on
    Kundenprojektname, Projektordner, and filename.

    Args:
        note_path: Vault-relative path to the existing note.
        project_name: Display name for the project in the PM database.
    """
    logger.info(
        "pm_create_project_from_note: project=%r note=%r", project_name, note_path,
    )

    # 1. Check Obsidian service
    obsidian_service = _get_obsidian_service(ctx)
    if not obsidian_service:
        return ERR_OBSIDIAN_NOT_LOADED

    # 2. Check required settings
    db = _get_db(ctx)
    for key in REQUIRED_SETTINGS_FROM_NOTE:
        err = _require_setting(db, key)
        if err:
            return err

    vault = db.get_setting(SETTING_PROJECT_VAULT)
    assert vault is not None

    # 3. Read note
    try:
        raw = obsidian_service.read_note(vault, note_path)
        data = json.loads(raw)
        content = data.get("content", "")
    except Exception as e:
        return f"ERROR: Failed to read note: {e}"

    # 4. Extract RTM tag and project folder
    proj_svc = ProjectService(db)
    rtm_tag = proj_svc.extract_rtm_tag(content)
    project_folder = proj_svc.extract_field(content, "Projektordner")

    # 5. Suggest synonyms
    suggestions = proj_svc.suggest_synonyms(content, note_path)

    # 6. Register project
    result = proj_svc.add_project(
        name=project_name,
        rtm_tag=rtm_tag,
        obsidian_vault=vault,
        obsidian_path=note_path,
        project_folder=project_folder,
    )

    # 7. Create project folder on disk if extracted (best-effort)
    folder_created = ""
    if project_folder:
        filesystem_service = _get_filesystem_service(ctx)
        if filesystem_service:
            base_path = db.get_setting(SETTING_PROJECT_FILES_BASE_PATH)
            if base_path:
                folder_path_full = f"{base_path}/{project_folder}"
                dir_result = filesystem_service.create_directory(folder_path_full)
                if dir_result.startswith("{"):
                    folder_created = f"Folder created: {folder_path_full}"

    # 8. Build response
    parts = [result]
    if rtm_tag:
        parts.append(f"RTM tag extracted: {rtm_tag}")
    else:
        parts.append("No RTM tag found in note.")
    parts.append(f"Note linked: {vault}/{note_path}")
    if folder_created:
        parts.append(folder_created)

    if suggestions:
        parts.append("")
        parts.append("Suggested synonyms:")
        field_labels = {"Kundenprojektname": "Kundenprojektname", "Projektordner": "Projektordner"}
        for s in suggestions:
            # Determine source
            source = "filename"
            for field, label in field_labels.items():
                if proj_svc.extract_field(content, field) == s:
                    source = label
                    break
            # Check if suggestion conflicts with existing synonym or project name
            conflict = ""
            name_match = db.get_project_by_name(s)
            if name_match:
                conflict = f" [conflicts with project name '{name_match.name}']"
            else:
                existing = db.get_synonym_with_project(s)
                if existing:
                    _, owner = existing
                    conflict = f" [already assigned to '{owner.name}']"
            parts.append(f"- {s} (from {source}){conflict}")
        parts.append("")
        parts.append("To add synonyms, ask the user which ones to keep.")

    return "\n".join(parts)


def pm_store_file_in_project(
    ctx: RunContext[Deps],
    project_name: str,
    source_file_path: str,
    source_type: str = "email",
) -> str:
    """Store a file in a project's Source folder.

    Creates {base_path}/{project_folder}/Source/{YYYYMMDD}_{source_type}/
    and copies the file there.

    Args:
        project_name: Project name or synonym to look up.
        source_file_path: Absolute path to the file to copy.
        source_type: Source category — "email" or "download".
    """
    logger.info(
        "pm_store_file_in_project: project=%r source=%r type=%r",
        project_name, source_file_path, source_type,
    )

    # 1. Get filesystem service
    filesystem_service = _get_filesystem_service(ctx)
    if not filesystem_service:
        return ERR_FILESYSTEM_NOT_LOADED

    # 2. Find project
    db = _get_db(ctx)
    proj_svc = ProjectService(db)
    project = proj_svc.find_project(project_name)
    if not project:
        return ERR_PROJECT_NOT_FOUND.format(reference=project_name)

    # 3. Check project folder
    if not project.project_folder:
        return ERR_PROJECT_NO_FOLDER.format(name=project.name)

    # 4. Get base path setting
    err = _require_setting(db, SETTING_PROJECT_FILES_BASE_PATH)
    if err:
        return err
    base_path = db.get_setting(SETTING_PROJECT_FILES_BASE_PATH)
    assert base_path is not None

    # 5. Build target directory
    date_str = datetime.now(tz=UTC).strftime("%Y%m%d")
    target_dir = f"{base_path}/{project.project_folder}/Source/{date_str}_{source_type}"

    # 6. Create directory
    dir_result = filesystem_service.create_directory(target_dir)
    if not dir_result.startswith("{"):
        return dir_result

    # 7. Build target file path and copy
    filename = PurePosixPath(source_file_path).name
    target_file = f"{target_dir}/{filename}"
    copy_result = filesystem_service.copy_file(source_file_path, target_file)
    if not copy_result.startswith("{"):
        return copy_result

    return f"File stored: {target_file}"


def pm_check_synonym_conflicts(ctx: RunContext[Deps]) -> str:
    """Check all projects for synonym conflicts (synonym matching another project name)."""
    logger.info("pm_check_synonym_conflicts")
    db = _get_db(ctx)
    proj_svc = ProjectService(db)
    return proj_svc.check_synonym_conflicts()
