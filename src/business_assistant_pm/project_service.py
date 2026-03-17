"""Project and synonym management service."""

from __future__ import annotations

import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .constants import (
    ERR_INVALID_MATCH_RULE_TYPE,
    ERR_MATCH_RULE_NOT_FOUND,
    ERR_PROJECT_NOT_FOUND,
    ERR_PROJECT_SYNONYM_NOT_FOUND,
    ERR_SYNONYM_ALREADY_EXISTS,
    ERR_SYNONYM_CONFLICTS_WITH_PROJECT_NAME,
    ERR_SYNONYM_EXISTS_OTHER_PROJECT,
    MATCH_RULE_OBSIDIAN_FIELDS,
    MATCH_SCORE_HARD,
    MATCH_SCORE_NAME,
    MATCH_SCORE_SOFT,
    OBSIDIAN_SECTION_PROJECT_UPDATES,
    VALID_MATCH_RULE_TYPES,
)
from .database import PmDatabase, PmProject, PmProjectMatchRule


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
        timetracking_project_id: str | None = None,
    ) -> str:
        """Add a new project. Returns confirmation message."""
        try:
            project = self._db.add_project(
                name=name,
                rtm_tag=rtm_tag,
                obsidian_vault=obsidian_vault,
                obsidian_path=obsidian_path,
                project_folder=project_folder,
                timetracking_project_id=timetracking_project_id,
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

        # Sync match rules (full replace)
        match_rules = self.extract_matching_section(content)
        self._db.delete_match_rules_for_project(project.id)
        rules_count = 0
        for rule_type, values in match_rules.items():
            for value in values:
                self._db.add_match_rule(project.id, rule_type, value)
                rules_count += 1

        parts: list[str] = []
        if rtm_tag:
            parts.append(f"RTM tag: {rtm_tag}")
        if project_folder:
            parts.append(f"Project folder: {project_folder}")
        if rules_count:
            parts.append(f"Match rules: {rules_count}")

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

    @staticmethod
    def extract_matching_section(note_content: str) -> dict[str, list[str]]:
        """Parse **Matching** section from Obsidian note content.

        Expected format:
            **Matching**
            email_domains: dyadic-agency.com, other.com
            project_numbers: 260086
            contacts: user@domain.com
            keywords: DC Jump n Run, HMI 2026

        Returns dict mapping rule_type to list of values.
        """
        match = re.search(
            r"\*\*Matching\*\*\s*\n(.*?)(?=\n\*\*|\Z)",
            note_content,
            re.DOTALL,
        )
        if not match:
            return {}

        # Reverse mapping: obsidian field name -> rule type
        field_to_type = {v: k for k, v in MATCH_RULE_OBSIDIAN_FIELDS.items()}

        result: dict[str, list[str]] = {}
        for line in match.group(1).strip().splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            field_name, _, raw_values = line.partition(":")
            field_name = field_name.strip()
            rule_type = field_to_type.get(field_name)
            if not rule_type:
                continue
            values = [v.strip() for v in raw_values.split(",") if v.strip()]
            if values:
                result[rule_type] = values
        return result

    @staticmethod
    def build_matching_section(rules: list[PmProjectMatchRule]) -> str:
        """Build **Matching** section markdown from a list of match rules."""
        grouped: dict[str, list[str]] = {}
        for rule in rules:
            grouped.setdefault(rule.rule_type, []).append(rule.value)

        lines = ["**Matching**"]
        for rule_type, field_name in MATCH_RULE_OBSIDIAN_FIELDS.items():
            if rule_type in grouped:
                lines.append(f"{field_name}: {', '.join(grouped[rule_type])}")
        return "\n".join(lines)

    def update_obsidian_matching_section(
        self,
        project: PmProject,
        obsidian_service: Any,
    ) -> str | None:
        """Update the **Matching** section in the project's Obsidian note."""
        vault = project.obsidian_vault
        path = project.obsidian_path
        if not vault or not path:
            return None

        try:
            raw = obsidian_service.read_note(vault, path)
            data = json.loads(raw)
            content = data.get("content", "")
        except Exception:
            return None

        rules = self._db.get_match_rules_for_project(project.id)
        new_section = self.build_matching_section(rules)

        # Replace existing section or append
        if re.search(r"\*\*Matching\*\*", content):
            content = re.sub(
                r"\*\*Matching\*\*\s*\n.*?(?=\n\*\*|\Z)",
                new_section,
                content,
                flags=re.DOTALL,
            )
        else:
            content = content.rstrip() + "\n\n" + new_section + "\n"

        try:
            obsidian_service.edit_note(vault, path, content, mode="replace")
        except Exception:
            return None

        return "Obsidian note updated."

    def update_obsidian_field(
        self,
        project: PmProject,
        obsidian_service: Any,
        field_name: str,
        new_value: str,
    ) -> str | None:
        """Update a **FieldName** value in the project's Obsidian note."""
        vault = project.obsidian_vault
        path = project.obsidian_path
        if not vault or not path:
            return None

        try:
            raw = obsidian_service.read_note(vault, path)
            data = json.loads(raw)
            content = data.get("content", "")
        except Exception:
            return None

        pattern = rf"(\*\*{re.escape(field_name)}\*\*\s*\n+\s*)\S.*?(?=\n|$)"
        if not re.search(pattern, content):
            return None

        content = re.sub(pattern, lambda m: m.group(1) + new_value, content, count=1)

        try:
            obsidian_service.edit_note(vault, path, content, mode="replace")
        except Exception:
            return None

        return "Obsidian note updated."

    def match_email_to_project(self, sender_email: str, subject: str) -> str:
        """Score-based email-to-project matching. Returns JSON."""
        all_rules = self._db.get_all_match_rules()
        projects = self._db.list_projects()

        # Index rules by project_id
        rules_by_project: dict[int, list[PmProjectMatchRule]] = {}
        for rule in all_rules:
            rules_by_project.setdefault(rule.project_id, []).append(rule)

        sender_lower = sender_email.lower()
        sender_domain = sender_lower.rsplit("@", 1)[-1] if "@" in sender_lower else ""
        subject_lower = subject.lower()

        best_score = 0
        best_match: dict[str, Any] | None = None

        for project in projects:
            score = 0
            matched_by = ""
            matched_value = ""

            # Check match rules
            for rule in rules_by_project.get(project.id, []):
                if rule.rule_type == "email_domain" and rule.value == sender_domain:
                    score += MATCH_SCORE_HARD
                    matched_by = "email_domain"
                    matched_value = rule.value
                elif rule.rule_type == "contact" and rule.value == sender_lower:
                    score += MATCH_SCORE_HARD
                    matched_by = "contact"
                    matched_value = rule.value
                elif rule.rule_type == "project_number" and rule.value in subject_lower:
                    score += MATCH_SCORE_HARD
                    matched_by = "project_number"
                    matched_value = rule.value
                elif rule.rule_type == "keyword" and rule.value in subject_lower:
                    score += MATCH_SCORE_SOFT
                    if not matched_by or matched_by == "keyword":
                        matched_by = "keyword"
                        matched_value = rule.value

            # Check project name in subject
            if project.name.lower() in subject_lower:
                score += MATCH_SCORE_NAME
                if not matched_by:
                    matched_by = "name"
                    matched_value = project.name

            # Check synonyms in subject
            synonyms = self._db.get_synonyms_for_project(project.id)
            for synonym in synonyms:
                if synonym in subject_lower:
                    score += MATCH_SCORE_NAME
                    if not matched_by:
                        matched_by = "synonym"
                        matched_value = synonym

            if score > best_score:
                best_score = score
                best_match = {
                    "project_name": project.name,
                    "score": score,
                    "matched_by": matched_by,
                    "matched_value": matched_value,
                }

        if best_match:
            return json.dumps(best_match)
        return json.dumps({"status": "no_match"})

    def add_match_rule(self, project_name: str, rule_type: str, value: str) -> str:
        """Add a match rule for a project. Returns confirmation."""
        if rule_type not in VALID_MATCH_RULE_TYPES:
            return ERR_INVALID_MATCH_RULE_TYPE.format(rule_type=rule_type)

        project = self._db.find_project_by_name_or_synonym(project_name)
        if not project:
            return ERR_PROJECT_NOT_FOUND.format(reference=project_name)

        self._db.add_match_rule(project.id, rule_type, value)
        return (
            f"Match rule added: {rule_type}='{value.lower()}' "
            f"for project '{project.name}'."
        )

    def remove_match_rule(self, project_name: str, rule_type: str, value: str) -> str:
        """Remove a match rule from a project. Returns confirmation."""
        project = self._db.find_project_by_name_or_synonym(project_name)
        if not project:
            return ERR_PROJECT_NOT_FOUND.format(reference=project_name)

        if self._db.delete_match_rule(project.id, rule_type, value):
            return (
                f"Match rule removed: {rule_type}='{value.lower()}' "
                f"from project '{project.name}'."
            )
        return ERR_MATCH_RULE_NOT_FOUND

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
                "timetracking_project_id": p.timetracking_project_id or "",
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
        if project.timetracking_project_id:
            parts.append(f"Timetracking Project ID: {project.timetracking_project_id}")
        if synonyms:
            parts.append(f"Synonyms: {', '.join(synonyms)}")

        # Include match rules
        rules = self._db.get_match_rules_for_project(project.id)
        if rules:
            grouped: dict[str, list[str]] = {}
            for rule in rules:
                grouped.setdefault(rule.rule_type, []).append(rule.value)
            parts.append("Match Rules:")
            for rtype, values in grouped.items():
                parts.append(f"  {rtype}: {', '.join(values)}")

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

    @staticmethod
    def _format_update_lines(content: str) -> list[str]:
        """Split content into non-empty stripped lines."""
        return [line.strip() for line in content.split("\n") if line.strip()]

    @staticmethod
    def _insert_update_into_section(
        note_content: str,
        today_str: str,
        lines: list[str],
    ) -> str:
        """Insert update lines into the ## Project Updates section.

        Creates the section if it does not exist. Groups entries under date headers.
        """
        if not lines:
            return note_content

        new_block = "\n".join(lines)
        section_re = re.compile(
            r"^" + re.escape(OBSIDIAN_SECTION_PROJECT_UPDATES) + r"[ \t]*$",
            re.MULTILINE,
        )
        section_match = section_re.search(note_content)

        if not section_match:
            # Section does not exist — append at end
            return (
                note_content.rstrip()
                + f"\n\n{OBSIDIAN_SECTION_PROJECT_UPDATES}\n{today_str}\n{new_block}\n"
            )

        # Find section boundaries
        section_start = section_match.end()
        next_heading = re.search(
            r"^## (?!Project Updates)", note_content[section_start:], re.MULTILINE,
        )
        section_end = section_start + next_heading.start() if next_heading else len(note_content)
        section_text = note_content[section_start:section_end]

        # Check if today's date already exists in the section
        date_re = re.compile(r"^" + re.escape(today_str) + r"[ \t]*$", re.MULTILINE)
        date_match = date_re.search(section_text)

        if date_match:
            # Find end of today's entry block (next date line or section end)
            after_date = date_match.end()
            next_date = re.search(
                r"^\d{4}-\d{2}-\d{2}[ \t]*$", section_text[after_date:], re.MULTILINE,
            )
            if next_date:
                insert_pos = section_start + after_date + next_date.start()
                # Insert before the trailing newline of last entry
                return (
                    note_content[:insert_pos].rstrip()
                    + "\n" + new_block + "\n"
                    + note_content[insert_pos:]
                )
            # No next date — insert at end of section
            insert_pos = section_end
            return (
                note_content[:insert_pos].rstrip()
                + "\n" + new_block + "\n"
                + note_content[insert_pos:]
            )

        # Today's date not found — add new date block at end of section
        insert_pos = section_end
        return (
            note_content[:insert_pos].rstrip()
            + f"\n{today_str}\n{new_block}\n"
            + note_content[insert_pos:]
        )

    @staticmethod
    def copy_file_to_resources(
        vault_path: str,
        note_path: str,
        file_path: str,
    ) -> tuple[str, str]:
        """Copy a file into the _resources subfolder next to the project note.

        Returns (vault_relative_resource_path, filename).
        """
        note_dir = str(Path(note_path).parent).replace("\\", "/")
        resources_rel = "_resources" if note_dir == "." else f"{note_dir}/_resources"

        resources_abs = Path(vault_path) / resources_rel
        resources_abs.mkdir(parents=True, exist_ok=True)

        src = Path(file_path)
        dest = resources_abs / src.name
        shutil.copy2(str(src), str(dest))

        vault_rel = f"{resources_rel}/{src.name}".replace("\\", "/")
        return vault_rel, src.name

    def append_project_update(
        self,
        project: PmProject,
        obsidian_service: Any,
        content: str,
        today_str: str,
        file_entries: list[str] | None = None,
    ) -> str:
        """Append an update to the ## Project Updates section in the Obsidian note.

        Args:
            project: The project with obsidian_vault and obsidian_path set.
            obsidian_service: The Obsidian service for reading/writing notes.
            content: The update text (can be multi-line).
            today_str: Today's date as YYYY-MM-DD string.
            file_entries: Optional list of vault-relative resource paths to embed.

        Returns:
            Confirmation message or error string.
        """
        vault = project.obsidian_vault
        path = project.obsidian_path
        if not vault or not path:
            return None  # type: ignore[return-value]

        raw = obsidian_service.read_note(vault, path)
        data = json.loads(raw)
        note_content = data.get("content", "")

        all_lines: list[str] = []
        if content:
            all_lines.extend(self._format_update_lines(content))
        if file_entries:
            for entry in file_entries:
                all_lines.append(f"![[{entry}]]")

        if not all_lines:
            return f"No content to add for project '{project.name}'."

        modified = self._insert_update_into_section(note_content, today_str, all_lines)
        obsidian_service.edit_note(vault, path, modified, mode="replace")

        return f"Project update added to '{project.name}' for {today_str}."
