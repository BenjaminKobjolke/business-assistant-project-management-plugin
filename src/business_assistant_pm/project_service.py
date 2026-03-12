"""Project and synonym management service."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

from .constants import (
    ERR_PROJECT_NOT_FOUND,
    ERR_PROJECT_SYNONYM_NOT_FOUND,
    ERR_SYNONYM_ALREADY_EXISTS,
    ERR_SYNONYM_CONFLICTS_WITH_PROJECT_NAME,
    ERR_SYNONYM_EXISTS_OTHER_PROJECT,
)
from .database import PmDatabase, PmProject


class ProjectService:
    """CRUD operations for projects and synonyms."""

    def __init__(self, db: PmDatabase) -> None:
        self._db = db

    def add_project(
        self,
        name: str,
        rtm_tag: str | None = None,
        obsidian_vault: str | None = None,
        obsidian_path: str | None = None,
        project_folder: str | None = None,
    ) -> str:
        """Add a new project. Returns confirmation message."""
        try:
            project = self._db.add_project(
                name=name,
                rtm_tag=rtm_tag,
                obsidian_vault=obsidian_vault,
                obsidian_path=obsidian_path,
                project_folder=project_folder,
            )
            return f"Project '{project.name}' created."
        except Exception as e:
            return f"Error creating project: {e}"

    def find_project(self, reference: str) -> PmProject | None:
        """Find a project by name or synonym (case-insensitive)."""
        return self._db.find_project_by_name_or_synonym(reference)

    def add_synonym(self, project_name: str, synonym: str) -> str:
        """Add a synonym for a project. Returns confirmation message."""
        project = self._db.get_project_by_name(project_name)
        if not project:
            return ERR_PROJECT_NOT_FOUND.format(reference=project_name)

        # Check if synonym conflicts with an existing project name
        name_match = self._db.get_project_by_name(synonym)
        if name_match:
            return ERR_SYNONYM_CONFLICTS_WITH_PROJECT_NAME.format(
                synonym=synonym, project_name=name_match.name,
            )

        # Check if synonym already exists for any project
        existing = self._db.get_synonym_with_project(synonym)
        if existing:
            _, owner = existing
            if owner.id == project.id:
                return ERR_SYNONYM_ALREADY_EXISTS.format(
                    synonym=synonym, project_name=project.name,
                )
            return ERR_SYNONYM_EXISTS_OTHER_PROJECT.format(
                synonym=synonym, project_name=owner.name,
            )

        try:
            self._db.add_synonym(project.id, synonym)
            return f"Synonym '{synonym}' added for project '{project.name}'."
        except Exception as e:
            return f"Error adding synonym: {e}"

    def remove_synonym(self, synonym: str) -> str:
        """Remove a project synonym. Returns confirmation message."""
        if self._db.delete_project_synonym(synonym):
            return f"Synonym '{synonym}' removed."
        return ERR_PROJECT_SYNONYM_NOT_FOUND.format(synonym=synonym)

    @staticmethod
    def extract_field(note_content: str, field_name: str) -> str | None:
        """Extract value following a bold heading like **FieldName** in note content."""
        pattern = rf"\*\*{re.escape(field_name)}\*\*\s*\n+\s*(\S.*?)(?:\n|$)"
        match = re.search(pattern, note_content)
        if match:
            value = match.group(1).strip()
            # Skip if the "value" is actually another bold heading
            if re.fullmatch(r"\*\*.+\*\*", value):
                return None
            return value
        return None

    @staticmethod
    def suggest_synonyms(note_content: str, note_path: str) -> list[str]:
        """Suggest synonyms from Kundenprojektname, Projektordner, and filename."""
        suggestions: list[str] = []
        for field in ("Kundenprojektname", "Projektordner"):
            val = ProjectService.extract_field(note_content, field)
            if val:
                suggestions.append(val)
        # filename stem
        filename = note_path.rsplit("/", 1)[-1].removesuffix(".md")
        if filename:
            suggestions.append(filename)
        # deduplicate case-insensitive, preserve first occurrence
        seen: set[str] = set()
        unique: list[str] = []
        for s in suggestions:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique.append(s)
        return unique

    @staticmethod
    def extract_rtm_tag(note_content: str) -> str | None:
        """Extract RTM tag from Obsidian note content.

        Looks for patterns like:
        **RTM Tag**

        #tag_value

        or:

        **RTM Tag**
        #tag_value
        """
        match = re.search(
            r"\*\*RTM Tag\*\*\s*\n+\s*\\?#(\S+)",
            note_content,
        )
        if match:
            return f"#{match.group(1)}"
        return None

    def sync_from_obsidian(
        self,
        project_name: str,
        obsidian_service: Any,
        vault: str,
        path: str,
    ) -> str:
        """Read an Obsidian note and extract RTM tag to update the project."""
        project = self._db.get_project_by_name(project_name)
        if not project:
            return f"Project '{project_name}' not found."

        try:
            result = obsidian_service.read_note(vault, path)
            data = json.loads(result)
            content = data.get("content", "")
        except Exception as e:
            return f"Error reading note: {e}"

        rtm_tag = self.extract_rtm_tag(content)
        project_folder = self.extract_field(content, "Projektordner")

        updates: dict[str, str] = {}
        if rtm_tag:
            updates["rtm_tag"] = rtm_tag
        if project_folder:
            updates["project_folder"] = project_folder

        if updates:
            self._db.update_project(project_name, **updates)

        parts: list[str] = []
        if rtm_tag:
            parts.append(f"RTM tag: {rtm_tag}")
        if project_folder:
            parts.append(f"Project folder: {project_folder}")

        if parts:
            return f"Project '{project_name}' synced. {', '.join(parts)}"
        return f"No RTM tag found in note for project '{project_name}'."

    def check_synonym_conflicts(self) -> str:
        """Check all projects for synonym conflicts. Returns JSON report."""
        projects = self._db.list_projects()
        conflicts: list[dict[str, str]] = []

        for project in projects:
            synonyms = self._db.get_synonyms_for_project(project.id)
            for synonym in synonyms:
                # Check if synonym matches another project's name
                name_match = self._db.get_project_by_name(synonym)
                if name_match and name_match.id != project.id:
                    conflicts.append({
                        "type": "synonym_matches_project_name",
                        "synonym": synonym,
                        "owned_by": project.name,
                        "conflicts_with": name_match.name,
                    })

        if not conflicts:
            return json.dumps({"status": "ok", "message": "No synonym conflicts found."})
        return json.dumps({"status": "conflicts_found", "conflicts": conflicts})

    def list_projects(self) -> str:
        """List all projects as JSON."""
        projects = self._db.list_projects()
        items = []
        for p in projects:
            item: dict = {
                "name": p.name,
                "rtm_tag": p.rtm_tag or "",
                "obsidian_vault": p.obsidian_vault or "",
                "obsidian_path": p.obsidian_path or "",
                "project_folder": p.project_folder or "",
            }
            synonyms = self._db.get_synonyms_for_project(p.id)
            if synonyms:
                item["synonyms"] = synonyms
            items.append(item)
        return json.dumps({"projects": items})

    def format_project_details(self, project: PmProject) -> str:
        """Format project details as a readable string."""
        synonyms = self._db.get_synonyms_for_project(project.id)
        parts = [f"Project: {project.name}"]
        if project.rtm_tag:
            parts.append(f"RTM Tag: {project.rtm_tag}")
        if project.obsidian_vault:
            parts.append(f"Obsidian: {project.obsidian_vault}/{project.obsidian_path}")
        if project.project_folder:
            parts.append(f"Project Folder: {project.project_folder}")
        if synonyms:
            parts.append(f"Synonyms: {', '.join(synonyms)}")
        return "\n".join(parts)

    @staticmethod
    def fill_template_fields(
        template_content: str,
        customer_name: str,
        rtm_tag: str,
        project_folder: str | None = None,
    ) -> str:
        """Fill Kundenprojektname, RTM Tag, and Projektordner fields in an Obsidian template."""
        result = re.sub(
            r"(\*\*Kundenprojektname\*\*\s*\n)\s*\n",
            rf"\g<1>{customer_name}\n\n",
            template_content,
            count=1,
        )
        result = re.sub(
            r"(\*\*RTM Tag\*\*\s*\n)\s*\n",
            rf"\g<1>{rtm_tag}\n\n",
            result,
            count=1,
        )
        if project_folder:
            result = re.sub(
                r"(\*\*Projektordner\*\*\s*\n)\s*\n",
                rf"\g<1>{project_folder}\n\n",
                result,
                count=1,
            )
        return result

    @staticmethod
    def build_project_note_path(folder_path: str, filename: str) -> str:
        """Build the full vault-relative path for a new project note."""
        year = str(datetime.now(tz=UTC).year)
        return f"{folder_path}/{year}/{filename}.md"
