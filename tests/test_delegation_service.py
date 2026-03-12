"""Tests for DelegationService."""

from __future__ import annotations

from business_assistant_pm.delegation_service import DelegationService


class TestDelegationService:
    def test_build_subject_basic(self) -> None:
        subject = DelegationService.build_delegation_subject(
            topic="Review document",
            priority="1",
            due="tomorrow",
        )
        assert subject == "Review document !1 ^tomorrow"

    def test_build_subject_with_tags(self) -> None:
        subject = DelegationService.build_delegation_subject(
            topic="Fix bug",
            priority="2",
            due="friday",
            rtm_tag="#p_project",
            contact_list_tag="#XIDA - Markus",
        )
        assert subject == "Fix bug !2 ^friday #p_project #XIDA - Markus"

    def test_build_subject_defaults(self) -> None:
        subject = DelegationService.build_delegation_subject(topic="Task")
        assert subject == "Task !2 ^tomorrow"

    def test_build_subject_no_rtm_tag(self) -> None:
        subject = DelegationService.build_delegation_subject(
            topic="Task",
            contact_list_tag="#list",
        )
        assert "#list" in subject
        # Only contact list tag, no extra space issues
        assert subject == "Task !2 ^tomorrow #list"

    def test_build_body(self) -> None:
        body = DelegationService.build_delegation_body(
            original_body="Please review this.",
            tracking_id="abc-123-def",
        )
        assert "Please review this." in body
        assert "[PM-TRACK:abc-123-def]" in body
        assert body.endswith("[PM-TRACK:abc-123-def]")

    def test_build_body_preserves_content(self) -> None:
        original = "Line 1\nLine 2\nLine 3"
        body = DelegationService.build_delegation_body(original, "tid")
        assert original in body
        assert "\n\n[PM-TRACK:tid]" in body

    def test_format_tracking_marker(self) -> None:
        marker = DelegationService.format_tracking_marker("uuid-value")
        assert marker == "[PM-TRACK:uuid-value]"
