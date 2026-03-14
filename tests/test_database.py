"""Tests for PM database operations."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text

from business_assistant_pm.database import PmDatabase


class TestSettings:
    def test_set_and_get_setting(self, db: PmDatabase) -> None:
        db.set_setting("todo_folder", "INBOX/Todo")
        assert db.get_setting("todo_folder") == "INBOX/Todo"

    def test_get_missing_setting(self, db: PmDatabase) -> None:
        assert db.get_setting("nonexistent") is None

    def test_update_setting(self, db: PmDatabase) -> None:
        db.set_setting("key", "value1")
        db.set_setting("key", "value2")
        assert db.get_setting("key") == "value2"

    def test_get_all_settings(self, db: PmDatabase) -> None:
        db.set_setting("a", "1")
        db.set_setting("b", "2")
        settings = db.get_all_settings()
        assert settings == {"a": "1", "b": "2"}


class TestProjects:
    def test_add_project(self, db: PmDatabase) -> None:
        project = db.add_project("Test Project", rtm_tag="#test")
        assert project.name == "Test Project"
        assert project.rtm_tag == "#test"
        assert project.id is not None

    def test_get_project_by_name(self, db: PmDatabase) -> None:
        db.add_project("My Project")
        project = db.get_project_by_name("My Project")
        assert project is not None
        assert project.name == "My Project"

    def test_get_project_by_name_case_insensitive(self, db: PmDatabase) -> None:
        db.add_project("My Project")
        project = db.get_project_by_name("my project")
        assert project is not None
        assert project.name == "My Project"

    def test_get_project_not_found(self, db: PmDatabase) -> None:
        assert db.get_project_by_name("Nonexistent") is None

    def test_find_by_name_or_synonym(self, db: PmDatabase) -> None:
        project = db.add_project("Full Name")
        db.add_synonym(project.id, "alias")
        found = db.find_project_by_name_or_synonym("alias")
        assert found is not None
        assert found.name == "Full Name"

    def test_find_by_name_direct(self, db: PmDatabase) -> None:
        db.add_project("Direct")
        found = db.find_project_by_name_or_synonym("Direct")
        assert found is not None

    def test_find_not_found(self, db: PmDatabase) -> None:
        assert db.find_project_by_name_or_synonym("nope") is None

    def test_add_project_with_folder(self, db: PmDatabase) -> None:
        project = db.add_project("Folder Project", project_folder="ACME_Folder")
        assert project.project_folder == "ACME_Folder"

    def test_update_project(self, db: PmDatabase) -> None:
        db.add_project("Updatable")
        result = db.update_project("Updatable", rtm_tag="#new_tag")
        assert result is True
        project = db.get_project_by_name("Updatable")
        assert project is not None
        assert project.rtm_tag == "#new_tag"

    def test_update_project_folder(self, db: PmDatabase) -> None:
        db.add_project("FolderUpdate")
        result = db.update_project("FolderUpdate", project_folder="NewFolder")
        assert result is True
        project = db.get_project_by_name("FolderUpdate")
        assert project is not None
        assert project.project_folder == "NewFolder"

    def test_add_project_with_timetracking_id(self, db: PmDatabase) -> None:
        project = db.add_project("TT Project", timetracking_project_id="tt-123")
        assert project.timetracking_project_id == "tt-123"

    def test_update_project_timetracking_id(self, db: PmDatabase) -> None:
        db.add_project("TTUpdate")
        result = db.update_project("TTUpdate", timetracking_project_id="tt-456")
        assert result is True
        project = db.get_project_by_name("TTUpdate")
        assert project is not None
        assert project.timetracking_project_id == "tt-456"

    def test_update_project_not_found(self, db: PmDatabase) -> None:
        assert db.update_project("Ghost", rtm_tag="#x") is False

    def test_list_projects(self, db: PmDatabase) -> None:
        db.add_project("A")
        db.add_project("B")
        projects = db.list_projects()
        assert len(projects) == 2


class TestSynonyms:
    def test_add_synonym(self, db: PmDatabase) -> None:
        project = db.add_project("Project")
        synonym = db.add_synonym(project.id, "Alias")
        assert synonym.synonym == "alias"
        assert synonym.project_id == project.id

    def test_get_synonyms_for_project(self, db: PmDatabase) -> None:
        project = db.add_project("Project")
        db.add_synonym(project.id, "One")
        db.add_synonym(project.id, "Two")
        synonyms = db.get_synonyms_for_project(project.id)
        assert set(synonyms) == {"one", "two"}

    def test_synonym_stored_lowercase(self, db: PmDatabase) -> None:
        project = db.add_project("Project")
        db.add_synonym(project.id, "MiXeD")
        synonyms = db.get_synonyms_for_project(project.id)
        assert synonyms == ["mixed"]

    def test_get_synonym_with_project(self, db: PmDatabase) -> None:
        project = db.add_project("Owner")
        db.add_synonym(project.id, "myalias")
        result = db.get_synonym_with_project("myalias")
        assert result is not None
        synonym_row, owner = result
        assert synonym_row.synonym == "myalias"
        assert owner.name == "Owner"

    def test_get_synonym_with_project_not_found(self, db: PmDatabase) -> None:
        assert db.get_synonym_with_project("nonexistent") is None

    def test_get_synonym_with_project_case_insensitive(self, db: PmDatabase) -> None:
        project = db.add_project("CaseProject")
        db.add_synonym(project.id, "mixed")
        result = db.get_synonym_with_project("MIXED")
        assert result is not None
        _, owner = result
        assert owner.name == "CaseProject"

    def test_add_synonym_idempotent_same_project(self, db: PmDatabase) -> None:
        project = db.add_project("Project")
        first = db.add_synonym(project.id, "Alias")
        second = db.add_synonym(project.id, "Alias")
        assert first.synonym == second.synonym
        assert first.project_id == second.project_id
        # Only one synonym row should exist
        assert db.get_synonyms_for_project(project.id) == ["alias"]

    def test_delete_project_synonym(self, db: PmDatabase) -> None:
        project = db.add_project("Project")
        db.add_synonym(project.id, "removable")
        result = db.delete_project_synonym("removable")
        assert result is True
        assert db.get_synonyms_for_project(project.id) == []

    def test_delete_project_synonym_not_found(self, db: PmDatabase) -> None:
        assert db.delete_project_synonym("ghost") is False


class TestWorkflows:
    def test_add_workflow(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Inbox Zero", "Step 1: Check emails")
        assert workflow.name == "Inbox Zero"
        assert workflow.instructions == "Step 1: Check emails"
        assert workflow.id is not None

    def test_get_workflow_by_name(self, db: PmDatabase) -> None:
        db.add_workflow("My Flow", "Do things")
        workflow = db.get_workflow_by_name("My Flow")
        assert workflow is not None
        assert workflow.name == "My Flow"

    def test_get_workflow_by_name_case_insensitive(self, db: PmDatabase) -> None:
        db.add_workflow("My Flow", "Do things")
        workflow = db.get_workflow_by_name("my flow")
        assert workflow is not None
        assert workflow.name == "My Flow"

    def test_get_workflow_not_found(self, db: PmDatabase) -> None:
        assert db.get_workflow_by_name("Nonexistent") is None

    def test_find_by_name_or_synonym(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Full Name", "instructions")
        db.add_workflow_synonym(workflow.id, "alias")
        found = db.find_workflow_by_name_or_synonym("alias")
        assert found is not None
        assert found.name == "Full Name"

    def test_find_by_name_direct(self, db: PmDatabase) -> None:
        db.add_workflow("Direct", "instructions")
        found = db.find_workflow_by_name_or_synonym("Direct")
        assert found is not None

    def test_find_not_found(self, db: PmDatabase) -> None:
        assert db.find_workflow_by_name_or_synonym("nope") is None

    def test_update_workflow(self, db: PmDatabase) -> None:
        db.add_workflow("Updatable", "old instructions")
        result = db.update_workflow("Updatable", "new instructions")
        assert result is True
        workflow = db.get_workflow_by_name("Updatable")
        assert workflow is not None
        assert workflow.instructions == "new instructions"

    def test_update_workflow_not_found(self, db: PmDatabase) -> None:
        assert db.update_workflow("Ghost", "instructions") is False

    def test_delete_workflow(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Deletable", "instructions")
        db.add_workflow_synonym(workflow.id, "del-alias")
        result = db.delete_workflow("Deletable")
        assert result is True
        assert db.get_workflow_by_name("Deletable") is None
        assert db.get_synonyms_for_workflow(workflow.id) == []

    def test_delete_workflow_not_found(self, db: PmDatabase) -> None:
        assert db.delete_workflow("Ghost") is False

    def test_list_workflows(self, db: PmDatabase) -> None:
        db.add_workflow("A", "instructions A")
        db.add_workflow("B", "instructions B")
        workflows = db.list_workflows()
        assert len(workflows) == 2


class TestWorkflowSynonyms:
    def test_add_workflow_synonym(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Flow", "instructions")
        synonym = db.add_workflow_synonym(workflow.id, "Alias")
        assert synonym.synonym == "alias"
        assert synonym.workflow_id == workflow.id

    def test_get_synonyms_for_workflow(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Flow", "instructions")
        db.add_workflow_synonym(workflow.id, "One")
        db.add_workflow_synonym(workflow.id, "Two")
        synonyms = db.get_synonyms_for_workflow(workflow.id)
        assert set(synonyms) == {"one", "two"}

    def test_synonym_stored_lowercase(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Flow", "instructions")
        db.add_workflow_synonym(workflow.id, "MiXeD")
        synonyms = db.get_synonyms_for_workflow(workflow.id)
        assert synonyms == ["mixed"]

    def test_delete_workflow_synonym(self, db: PmDatabase) -> None:
        workflow = db.add_workflow("Flow", "instructions")
        db.add_workflow_synonym(workflow.id, "removable")
        result = db.delete_workflow_synonym("removable")
        assert result is True
        assert db.get_synonyms_for_workflow(workflow.id) == []

    def test_delete_workflow_synonym_not_found(self, db: PmDatabase) -> None:
        assert db.delete_workflow_synonym("ghost") is False


class TestContacts:
    def test_set_contact(self, db: PmDatabase) -> None:
        contact = db.set_contact("Alice", "alice@example.com", "#alice_list")
        assert contact.name == "alice"
        assert contact.email == "alice@example.com"
        assert contact.rtm_list_tag == "#alice_list"

    def test_update_contact(self, db: PmDatabase) -> None:
        db.set_contact("bob", "bob@old.com")
        updated = db.set_contact("bob", "bob@new.com", "#bob_list")
        assert updated.email == "bob@new.com"
        assert updated.rtm_list_tag == "#bob_list"

    def test_get_contact(self, db: PmDatabase) -> None:
        db.set_contact("charlie", "charlie@example.com")
        contact = db.get_contact("Charlie")
        assert contact is not None
        assert contact.email == "charlie@example.com"

    def test_get_contact_not_found(self, db: PmDatabase) -> None:
        assert db.get_contact("nobody") is None

    def test_list_contacts(self, db: PmDatabase) -> None:
        db.set_contact("a", "a@example.com")
        db.set_contact("b", "b@example.com")
        contacts = db.list_contacts()
        assert len(contacts) == 2


class TestTracking:
    def test_create_tracking(self, db: PmDatabase) -> None:
        record = db.create_tracking(
            tracking_id="abc-123",
            email_id="email1",
            email_folder="INBOX/Todo",
            email_subject="Test",
            email_from="sender@example.com",
            task_name="Do something",
        )
        assert record.tracking_id == "abc-123"
        assert record.status == "active"

    def test_find_by_tracking_id(self, db: PmDatabase) -> None:
        db.create_tracking("tid-1", "e1", "INBOX")
        found = db.find_tracking_by_id("tid-1")
        assert found is not None
        assert found.email_id == "e1"

    def test_find_by_tracking_id_not_found(self, db: PmDatabase) -> None:
        assert db.find_tracking_by_id("missing") is None

    def test_find_by_rtm_task_id(self, db: PmDatabase) -> None:
        db.create_tracking("tid-2", "e2", "INBOX", rtm_task_id="1/2/3")
        found = db.find_tracking_by_rtm_task_id("1/2/3")
        assert found is not None
        assert found.tracking_id == "tid-2"

    def test_complete_tracking(self, db: PmDatabase) -> None:
        db.create_tracking("tid-3", "e3", "INBOX")
        result = db.complete_tracking("tid-3")
        assert result is True
        record = db.find_tracking_by_id("tid-3")
        assert record is not None
        assert record.status == "completed"
        assert record.completed_at is not None

    def test_complete_tracking_not_found(self, db: PmDatabase) -> None:
        assert db.complete_tracking("missing") is False

    def test_list_tracking_active(self, db: PmDatabase) -> None:
        db.create_tracking("t1", "e1", "F1")
        db.create_tracking("t2", "e2", "F2")
        db.complete_tracking("t2")
        active = db.list_tracking(status="active")
        assert len(active) == 1
        assert active[0].tracking_id == "t1"

    def test_list_tracking_by_delegate(self, db: PmDatabase) -> None:
        db.create_tracking("t1", "e1", "F1", delegated_to="alice")
        db.create_tracking("t2", "e2", "F2", delegated_to="bob")
        alice_records = db.list_tracking(delegated_to="alice")
        assert len(alice_records) == 1
        assert alice_records[0].delegated_to == "alice"


def _create_old_schema_db(db_path: Path) -> None:
    """Create a DB with the old pm_projects schema (no project_folder column)."""
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE pm_settings (key VARCHAR PRIMARY KEY, value TEXT)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_projects ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR UNIQUE, "
            "rtm_tag VARCHAR, "
            "obsidian_vault VARCHAR, "
            "obsidian_path VARCHAR, "
            "created_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_project_synonyms ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "synonym VARCHAR UNIQUE, "
            "project_id INTEGER)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_contacts ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR UNIQUE, "
            "email VARCHAR, "
            "rtm_list_tag VARCHAR)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_tracking ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "tracking_id VARCHAR UNIQUE, "
            "email_id VARCHAR, "
            "email_folder VARCHAR, "
            "email_subject VARCHAR, "
            "email_from VARCHAR, "
            "task_name VARCHAR, "
            "rtm_task_id VARCHAR, "
            "delegated_to VARCHAR, "
            "project_name VARCHAR, "
            "status VARCHAR, "
            "created_at DATETIME, "
            "completed_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_workflows ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name VARCHAR UNIQUE, "
            "instructions TEXT, "
            "created_at DATETIME)"
        ))
        conn.execute(text(
            "CREATE TABLE pm_workflow_synonyms ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "synonym VARCHAR UNIQUE, "
            "workflow_id INTEGER)"
        ))
    engine.dispose()


class TestAutoMigration:
    def test_missing_column_is_added(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_old_schema_db(db_path)
        db = PmDatabase(str(db_path))
        project = db.add_project("MigTest", project_folder="MyFolder")
        assert project.project_folder == "MyFolder"

    def test_migration_is_idempotent(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_old_schema_db(db_path)
        PmDatabase(str(db_path))
        PmDatabase(str(db_path))  # second init should not error

    def test_existing_data_preserved_after_migration(self, tmp_path: Path) -> None:
        db_path = tmp_path / "test.db"
        _create_old_schema_db(db_path)
        engine = create_engine(f"sqlite:///{db_path}", echo=False)
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO pm_projects (name, rtm_tag, created_at) "
                "VALUES ('OldProject', '#old', '2025-01-01 00:00:00')"
            ))
        engine.dispose()
        db = PmDatabase(str(db_path))
        project = db.get_project_by_name("OldProject")
        assert project is not None
        assert project.name == "OldProject"
        assert project.rtm_tag == "#old"
        assert project.project_folder is None
        assert project.timetracking_project_id is None
