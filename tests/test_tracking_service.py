"""Tests for TrackingService."""

from __future__ import annotations

from business_assistant_pm.database import PmDatabase
from business_assistant_pm.tracking_service import TrackingService


class TestTrackingService:
    def test_generate_tracking_id_is_uuid(self) -> None:
        tid = TrackingService.generate_tracking_id()
        assert len(tid) == 36
        assert tid.count("-") == 4

    def test_format_tracking_marker(self) -> None:
        marker = TrackingService.format_tracking_marker("abc-def-123")
        assert marker == "[PM-TRACK:abc-def-123]"

    def test_extract_tracking_id_found(self) -> None:
        text = "Hello\n\n[PM-TRACK:550e8400-e29b-41d4-a716-446655440000]\nEnd"
        tid = TrackingService.extract_tracking_id(text)
        assert tid == "550e8400-e29b-41d4-a716-446655440000"

    def test_extract_tracking_id_not_found(self) -> None:
        assert TrackingService.extract_tracking_id("no tracking here") is None

    def test_extract_tracking_id_partial_no_match(self) -> None:
        assert TrackingService.extract_tracking_id("[PM-TRACK:short]") is None

    def test_create_tracking(self, db: PmDatabase) -> None:
        svc = TrackingService(db)
        tid = svc.create_tracking(
            email_id="e1",
            email_folder="INBOX",
            email_subject="Test",
            email_from="sender@example.com",
            task_name="Task 1",
        )
        assert len(tid) == 36
        record = svc.find_by_tracking_id(tid)
        assert record is not None
        assert record.email_id == "e1"
        assert record.task_name == "Task 1"

    def test_find_by_rtm_task_id(self, db: PmDatabase) -> None:
        svc = TrackingService(db)
        tid = svc.create_tracking(
            email_id="e2",
            email_folder="INBOX",
            rtm_task_id="1/2/3",
        )
        record = svc.find_by_rtm_task_id("1/2/3")
        assert record is not None
        assert record.tracking_id == tid

    def test_complete_tracking(self, db: PmDatabase) -> None:
        svc = TrackingService(db)
        tid = svc.create_tracking(email_id="e3", email_folder="F")
        assert svc.complete_tracking(tid) is True
        record = svc.find_by_tracking_id(tid)
        assert record is not None
        assert record.status == "completed"

    def test_list_active(self, db: PmDatabase) -> None:
        svc = TrackingService(db)
        svc.create_tracking(email_id="e1", email_folder="F")
        svc.create_tracking(email_id="e2", email_folder="F", delegated_to="alice")
        active = svc.list_active()
        assert len(active) == 2
        alice = svc.list_active(delegated_to="alice")
        assert len(alice) == 1
