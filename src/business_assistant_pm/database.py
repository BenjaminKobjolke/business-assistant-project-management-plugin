"""SQLAlchemy models and database operations for PM plugin."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import DateTime, String, Text, create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


class PmSettingRow(Base):
    """Runtime settings (key-value store)."""

    __tablename__ = "pm_settings"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class PmProject(Base):
    """Projects with metadata."""

    __tablename__ = "pm_projects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    rtm_tag: Mapped[str | None] = mapped_column(String, default=None)
    obsidian_vault: Mapped[str | None] = mapped_column(String, default=None)
    obsidian_path: Mapped[str | None] = mapped_column(String, default=None)
    project_folder: Mapped[str | None] = mapped_column(String, default=None)
    timetracking_project_id: Mapped[str | None] = mapped_column(String, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC),
    )


class PmProjectSynonym(Base):
    """Project synonyms (case-insensitive)."""

    __tablename__ = "pm_project_synonyms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    synonym: Mapped[str] = mapped_column(String, unique=True)
    project_id: Mapped[int] = mapped_column()


class PmProjectMatchRule(Base):
    """Project matching rules for email-to-project matching."""

    __tablename__ = "pm_project_match_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column()
    rule_type: Mapped[str] = mapped_column(String)  # email_domain|contact|project_number|keyword
    value: Mapped[str] = mapped_column(String)  # stored lowercase


class PmWorkflow(Base):
    """Reusable named workflows with AI instructions."""

    __tablename__ = "pm_workflows"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    instructions: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC),
    )


class PmWorkflowSynonym(Base):
    """Workflow synonyms (case-insensitive)."""

    __tablename__ = "pm_workflow_synonyms"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    synonym: Mapped[str] = mapped_column(String, unique=True)
    workflow_id: Mapped[int] = mapped_column()


class PmContact(Base):
    """Delegation contacts."""

    __tablename__ = "pm_contacts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String)
    rtm_list_tag: Mapped[str | None] = mapped_column(String, default=None)


class PmTracking(Base):
    """Email-task tracking records."""

    __tablename__ = "pm_tracking"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracking_id: Mapped[str] = mapped_column(String, unique=True)
    email_id: Mapped[str] = mapped_column(String)
    email_folder: Mapped[str] = mapped_column(String)
    email_subject: Mapped[str] = mapped_column(String, default="")
    email_from: Mapped[str] = mapped_column(String, default="")
    task_name: Mapped[str] = mapped_column(String, default="")
    rtm_task_id: Mapped[str | None] = mapped_column(String, default=None)
    delegated_to: Mapped[str | None] = mapped_column(String, default=None)
    project_name: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC),
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, default=None)


class PmDatabase:
    """Database operations for PM plugin."""

    def __init__(self, db_path: str) -> None:
        if db_path == ":memory:":
            self._engine = create_engine("sqlite:///:memory:", echo=False)
        else:
            path = Path(db_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self._engine = create_engine(f"sqlite:///{path}", echo=False)
        Base.metadata.create_all(self._engine)
        self._migrate_add_missing_columns()
        self._session_factory = sessionmaker(bind=self._engine, expire_on_commit=False)

    def _migrate_add_missing_columns(self) -> None:
        """Add columns present in models but missing from existing tables."""
        insp = inspect(self._engine)
        for table_name, table in Base.metadata.tables.items():
            try:
                existing = {col["name"] for col in insp.get_columns(table_name)}
            except Exception:
                continue
            for col in table.columns:
                if col.name not in existing:
                    col_type = col.type.compile(dialect=self._engine.dialect)
                    with self._engine.begin() as conn:
                        conn.execute(
                            text(
                                f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}"
                            )
                        )
                    logger.info("Added column %s.%s (%s)", table_name, col.name, col_type)

    def _open(self) -> Session:
        """Open a new session."""
        return self._session_factory()

    # --- Settings ---

    def get_setting(self, key: str) -> str | None:
        """Get a setting value by key."""
        with self._open() as session:
            row = session.query(PmSettingRow).filter(PmSettingRow.key == key).first()
            if row:
                return row.value
        return None

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value (insert or update)."""
        with self._open() as session:
            existing = session.query(PmSettingRow).filter(PmSettingRow.key == key).first()
            if existing:
                existing.value = value
            else:
                session.add(PmSettingRow(key=key, value=value))
            session.commit()

    def get_all_settings(self) -> dict[str, str]:
        """Get all settings as a dict."""
        with self._open() as session:
            rows = session.query(PmSettingRow).all()
            return {row.key: row.value for row in rows}

    # --- Projects ---

    def add_project(
        self,
        name: str,
        rtm_tag: str | None = None,
        obsidian_vault: str | None = None,
        obsidian_path: str | None = None,
        project_folder: str | None = None,
        timetracking_project_id: str | None = None,
    ) -> PmProject:
        """Add a new project."""
        with self._open() as session:
            project = PmProject(
                name=name,
                rtm_tag=rtm_tag,
                obsidian_vault=obsidian_vault,
                obsidian_path=obsidian_path,
                project_folder=project_folder,
                timetracking_project_id=timetracking_project_id,
                created_at=datetime.now(UTC),
            )
            session.add(project)
            session.commit()
            session.expunge(project)
            return project

    def get_project_by_name(self, name: str) -> PmProject | None:
        """Get a project by exact name (case-insensitive)."""
        with self._open() as session:
            project = (
                session.query(PmProject)
                .filter(PmProject.name.ilike(name))
                .first()
            )
            if project:
                session.expunge(project)
            return project

    def find_project_by_name_or_synonym(self, reference: str) -> PmProject | None:
        """Find a project by name or synonym (case-insensitive)."""
        # Try exact name match first
        project = self.get_project_by_name(reference)
        if project:
            return project

        # Try synonym match
        with self._open() as session:
            synonym = (
                session.query(PmProjectSynonym)
                .filter(PmProjectSynonym.synonym == reference.lower())
                .first()
            )
            if synonym:
                project = (
                    session.query(PmProject)
                    .filter(PmProject.id == synonym.project_id)
                    .first()
                )
                if project:
                    session.expunge(project)
                    return project
        return None

    def update_project(
        self,
        name: str,
        rtm_tag: str | None = None,
        obsidian_vault: str | None = None,
        obsidian_path: str | None = None,
        project_folder: str | None = None,
        timetracking_project_id: str | None = None,
    ) -> bool:
        """Update project fields."""
        with self._open() as session:
            project = (
                session.query(PmProject)
                .filter(PmProject.name.ilike(name))
                .first()
            )
            if not project:
                return False
            if rtm_tag is not None:
                project.rtm_tag = rtm_tag
            if obsidian_vault is not None:
                project.obsidian_vault = obsidian_vault
            if obsidian_path is not None:
                project.obsidian_path = obsidian_path
            if project_folder is not None:
                project.project_folder = project_folder
            if timetracking_project_id is not None:
                project.timetracking_project_id = timetracking_project_id
            session.commit()
            return True

    def list_projects(self) -> list[PmProject]:
        """List all projects."""
        with self._open() as session:
            projects = session.query(PmProject).all()
            for p in projects:
                session.expunge(p)
            return projects

    # --- Synonyms ---

    def add_synonym(self, project_id: int, synonym: str) -> PmProjectSynonym:
        """Add a synonym for a project. Idempotent for the same project."""
        with self._open() as session:
            existing = (
                session.query(PmProjectSynonym)
                .filter(PmProjectSynonym.synonym == synonym.lower())
                .first()
            )
            if existing and existing.project_id == project_id:
                session.expunge(existing)
                return existing
            row = PmProjectSynonym(
                synonym=synonym.lower(),
                project_id=project_id,
            )
            session.add(row)
            session.commit()
            session.expunge(row)
            return row

    def get_synonyms_for_project(self, project_id: int) -> list[str]:
        """Get all synonyms for a project."""
        with self._open() as session:
            rows = (
                session.query(PmProjectSynonym)
                .filter(PmProjectSynonym.project_id == project_id)
                .all()
            )
            return [r.synonym for r in rows]

    def get_synonym_with_project(self, synonym: str) -> tuple[PmProjectSynonym, PmProject] | None:
        """Look up a synonym and its owning project. Returns None if not found."""
        with self._open() as session:
            row = (
                session.query(PmProjectSynonym)
                .filter(PmProjectSynonym.synonym == synonym.lower())
                .first()
            )
            if not row:
                return None
            project = (
                session.query(PmProject)
                .filter(PmProject.id == row.project_id)
                .first()
            )
            if not project:
                return None
            session.expunge(row)
            session.expunge(project)
            return (row, project)

    def delete_project_synonym(self, synonym: str) -> bool:
        """Delete a project synonym."""
        with self._open() as session:
            row = (
                session.query(PmProjectSynonym)
                .filter(PmProjectSynonym.synonym == synonym.lower())
                .first()
            )
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    # --- Match Rules ---

    def add_match_rule(
        self, project_id: int, rule_type: str, value: str,
    ) -> PmProjectMatchRule:
        """Add a match rule for a project. Idempotent."""
        lower_value = value.lower()
        with self._open() as session:
            existing = (
                session.query(PmProjectMatchRule)
                .filter(
                    PmProjectMatchRule.project_id == project_id,
                    PmProjectMatchRule.rule_type == rule_type,
                    PmProjectMatchRule.value == lower_value,
                )
                .first()
            )
            if existing:
                session.expunge(existing)
                return existing
            row = PmProjectMatchRule(
                project_id=project_id,
                rule_type=rule_type,
                value=lower_value,
            )
            session.add(row)
            session.commit()
            session.expunge(row)
            return row

    def get_match_rules_for_project(self, project_id: int) -> list[PmProjectMatchRule]:
        """Get all match rules for a project."""
        with self._open() as session:
            rows = (
                session.query(PmProjectMatchRule)
                .filter(PmProjectMatchRule.project_id == project_id)
                .all()
            )
            for r in rows:
                session.expunge(r)
            return rows

    def get_all_match_rules(self) -> list[PmProjectMatchRule]:
        """Get all match rules across all projects."""
        with self._open() as session:
            rows = session.query(PmProjectMatchRule).all()
            for r in rows:
                session.expunge(r)
            return rows

    def delete_match_rule(
        self, project_id: int, rule_type: str, value: str,
    ) -> bool:
        """Delete a specific match rule."""
        lower_value = value.lower()
        with self._open() as session:
            row = (
                session.query(PmProjectMatchRule)
                .filter(
                    PmProjectMatchRule.project_id == project_id,
                    PmProjectMatchRule.rule_type == rule_type,
                    PmProjectMatchRule.value == lower_value,
                )
                .first()
            )
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    def delete_match_rules_for_project(self, project_id: int) -> int:
        """Delete all match rules for a project. Returns count deleted."""
        with self._open() as session:
            count = (
                session.query(PmProjectMatchRule)
                .filter(PmProjectMatchRule.project_id == project_id)
                .delete()
            )
            session.commit()
            return count

    # --- Workflows ---

    def add_workflow(self, name: str, instructions: str) -> PmWorkflow:
        """Add a new workflow."""
        with self._open() as session:
            workflow = PmWorkflow(
                name=name,
                instructions=instructions,
                created_at=datetime.now(UTC),
            )
            session.add(workflow)
            session.commit()
            session.expunge(workflow)
            return workflow

    def get_workflow_by_name(self, name: str) -> PmWorkflow | None:
        """Get a workflow by exact name (case-insensitive)."""
        with self._open() as session:
            workflow = (
                session.query(PmWorkflow)
                .filter(PmWorkflow.name.ilike(name))
                .first()
            )
            if workflow:
                session.expunge(workflow)
            return workflow

    def find_workflow_by_name_or_synonym(self, reference: str) -> PmWorkflow | None:
        """Find a workflow by name or synonym (case-insensitive)."""
        workflow = self.get_workflow_by_name(reference)
        if workflow:
            return workflow

        with self._open() as session:
            synonym = (
                session.query(PmWorkflowSynonym)
                .filter(PmWorkflowSynonym.synonym == reference.lower())
                .first()
            )
            if synonym:
                workflow = (
                    session.query(PmWorkflow)
                    .filter(PmWorkflow.id == synonym.workflow_id)
                    .first()
                )
                if workflow:
                    session.expunge(workflow)
                    return workflow
        return None

    def update_workflow(self, name: str, instructions: str) -> bool:
        """Update workflow instructions."""
        with self._open() as session:
            workflow = (
                session.query(PmWorkflow)
                .filter(PmWorkflow.name.ilike(name))
                .first()
            )
            if not workflow:
                return False
            workflow.instructions = instructions
            session.commit()
            return True

    def delete_workflow(self, name: str) -> bool:
        """Delete a workflow and its synonyms."""
        with self._open() as session:
            workflow = (
                session.query(PmWorkflow)
                .filter(PmWorkflow.name.ilike(name))
                .first()
            )
            if not workflow:
                return False
            session.query(PmWorkflowSynonym).filter(
                PmWorkflowSynonym.workflow_id == workflow.id,
            ).delete()
            session.delete(workflow)
            session.commit()
            return True

    def list_workflows(self) -> list[PmWorkflow]:
        """List all workflows."""
        with self._open() as session:
            workflows = session.query(PmWorkflow).all()
            for w in workflows:
                session.expunge(w)
            return workflows

    # --- Workflow Synonyms ---

    def add_workflow_synonym(self, workflow_id: int, synonym: str) -> PmWorkflowSynonym:
        """Add a synonym for a workflow."""
        with self._open() as session:
            row = PmWorkflowSynonym(
                synonym=synonym.lower(),
                workflow_id=workflow_id,
            )
            session.add(row)
            session.commit()
            session.expunge(row)
            return row

    def get_synonyms_for_workflow(self, workflow_id: int) -> list[str]:
        """Get all synonyms for a workflow."""
        with self._open() as session:
            rows = (
                session.query(PmWorkflowSynonym)
                .filter(PmWorkflowSynonym.workflow_id == workflow_id)
                .all()
            )
            return [r.synonym for r in rows]

    def delete_workflow_synonym(self, synonym: str) -> bool:
        """Delete a workflow synonym."""
        with self._open() as session:
            row = (
                session.query(PmWorkflowSynonym)
                .filter(PmWorkflowSynonym.synonym == synonym.lower())
                .first()
            )
            if not row:
                return False
            session.delete(row)
            session.commit()
            return True

    # --- Contacts ---

    def set_contact(
        self, name: str, email: str, rtm_list_tag: str | None = None,
    ) -> PmContact:
        """Add or update a delegation contact."""
        with self._open() as session:
            existing = (
                session.query(PmContact)
                .filter(PmContact.name == name.lower())
                .first()
            )
            if existing:
                existing.email = email
                if rtm_list_tag is not None:
                    existing.rtm_list_tag = rtm_list_tag
                session.commit()
                session.expunge(existing)
                return existing
            contact = PmContact(
                name=name.lower(),
                email=email,
                rtm_list_tag=rtm_list_tag,
            )
            session.add(contact)
            session.commit()
            session.expunge(contact)
            return contact

    def get_contact(self, name: str) -> PmContact | None:
        """Get a contact by name (case-insensitive)."""
        with self._open() as session:
            contact = (
                session.query(PmContact)
                .filter(PmContact.name == name.lower())
                .first()
            )
            if contact:
                session.expunge(contact)
            return contact

    def list_contacts(self) -> list[PmContact]:
        """List all contacts."""
        with self._open() as session:
            contacts = session.query(PmContact).all()
            for c in contacts:
                session.expunge(c)
            return contacts

    # --- Tracking ---

    def create_tracking(
        self,
        tracking_id: str,
        email_id: str,
        email_folder: str,
        email_subject: str = "",
        email_from: str = "",
        task_name: str = "",
        rtm_task_id: str | None = None,
        delegated_to: str | None = None,
        project_name: str | None = None,
    ) -> PmTracking:
        """Create a new tracking record."""
        with self._open() as session:
            record = PmTracking(
                tracking_id=tracking_id,
                email_id=email_id,
                email_folder=email_folder,
                email_subject=email_subject,
                email_from=email_from,
                task_name=task_name,
                rtm_task_id=rtm_task_id,
                delegated_to=delegated_to,
                project_name=project_name,
                status="active",
                created_at=datetime.now(UTC),
            )
            session.add(record)
            session.commit()
            session.expunge(record)
            return record

    def find_tracking_by_id(self, tracking_id: str) -> PmTracking | None:
        """Find a tracking record by tracking ID."""
        with self._open() as session:
            record = (
                session.query(PmTracking)
                .filter(PmTracking.tracking_id == tracking_id)
                .first()
            )
            if record:
                session.expunge(record)
            return record

    def find_tracking_by_rtm_task_id(self, rtm_task_id: str) -> PmTracking | None:
        """Find a tracking record by RTM task ID."""
        with self._open() as session:
            record = (
                session.query(PmTracking)
                .filter(PmTracking.rtm_task_id == rtm_task_id)
                .first()
            )
            if record:
                session.expunge(record)
            return record

    def complete_tracking(self, tracking_id: str) -> bool:
        """Mark a tracking record as completed."""
        with self._open() as session:
            record = (
                session.query(PmTracking)
                .filter(PmTracking.tracking_id == tracking_id)
                .first()
            )
            if not record:
                return False
            record.status = "completed"
            record.completed_at = datetime.now(UTC)
            session.commit()
            return True

    def list_tracking(
        self, status: str = "active", delegated_to: str = "",
    ) -> list[PmTracking]:
        """List tracking records filtered by status and optional delegate."""
        with self._open() as session:
            query = session.query(PmTracking).filter(PmTracking.status == status)
            if delegated_to:
                query = query.filter(PmTracking.delegated_to == delegated_to.lower())
            records = query.all()
            for r in records:
                session.expunge(r)
            return records
