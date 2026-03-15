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

    def test_build_body_with_prefix_message(self) -> None:
        body = DelegationService.build_delegation_body(
            original_body="Original content.",
            tracking_id="abc-123",
            prefix_message="Kannst du bitte den Aufwand schätzen",
        )
        assert body.startswith("Kannst du bitte den Aufwand schätzen")
        assert "---" in body
        assert "Original content." in body
        assert body.endswith("[PM-TRACK:abc-123]")
        # Verify order: prefix, separator, original, marker
        prefix_pos = body.index("Kannst du")
        separator_pos = body.index("---")
        original_pos = body.index("Original content.")
        marker_pos = body.index("[PM-TRACK:")
        assert prefix_pos < separator_pos < original_pos < marker_pos

    def test_build_body_without_prefix_message(self) -> None:
        body = DelegationService.build_delegation_body(
            original_body="Content here.",
            tracking_id="tid-456",
        )
        assert body.startswith("Content here.")
        assert body.endswith("[PM-TRACK:tid-456]")

    def test_build_body_html_preserves_formatting(self) -> None:
        html_content = "<html><body><p>Hello</p></body></html>"
        body = DelegationService.build_delegation_body(
            original_body=html_content,
            tracking_id="html-tid",
        )
        assert html_content in body
        assert "<p>[PM-TRACK:html-tid]</p>" in body

    def test_build_body_html_with_prefix(self) -> None:
        html_content = "<html><body><p>Original</p></body></html>"
        body = DelegationService.build_delegation_body(
            original_body=html_content,
            tracking_id="html-tid",
            prefix_message="Bitte prüfen",
        )
        assert "<p>Bitte prüfen</p><br><hr><br>" in body
        assert html_content in body
        assert "<p>[PM-TRACK:html-tid]</p>" in body
        # Verify order: prefix before original before marker
        prefix_pos = body.index("<p>Bitte prüfen</p>")
        original_pos = body.index(html_content)
        marker_pos = body.index("<p>[PM-TRACK:")
        assert prefix_pos < original_pos < marker_pos

    def test_format_tracking_marker(self) -> None:
        marker = DelegationService.format_tracking_marker("uuid-value")
        assert marker == "[PM-TRACK:uuid-value]"
