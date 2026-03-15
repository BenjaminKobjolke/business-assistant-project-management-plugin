"""Delegation email composition service."""

from __future__ import annotations

from .constants import TRACKING_ID_FORMAT


class DelegationService:
    """Builds delegation email subjects and bodies with RTM Smart Add syntax."""

    @staticmethod
    def build_delegation_subject(
        topic: str,
        priority: str = "2",
        due: str = "tomorrow",
        rtm_tag: str = "",
        contact_list_tag: str = "",
    ) -> str:
        """Build a delegation email subject using RTM Smart Add syntax.

        Format: "Topic !priority ^due #rtm_tag #contact_list_tag"
        """
        parts = [topic, f"!{priority}", f"^{due}"]
        if rtm_tag:
            parts.append(rtm_tag)
        if contact_list_tag:
            parts.append(contact_list_tag)
        return " ".join(parts)

    @staticmethod
    def build_delegation_body(
        original_body: str,
        tracking_id: str,
        prefix_message: str = "",
    ) -> str:
        """Build delegation email body with optional prefix and tracking marker."""
        raw_marker = TRACKING_ID_FORMAT.format(tracking_id=tracking_id)
        is_html = "<html" in original_body.lower() or "<body" in original_body.lower()

        if is_html:
            prefix_html = f"<p>{prefix_message}</p><br><hr><br>" if prefix_message else ""
            marker_html = f"<p>{raw_marker}</p>"
            parts = [p for p in [prefix_html, original_body, marker_html] if p]
            return "\n".join(parts)

        parts = []
        if prefix_message:
            parts.append(prefix_message)
            parts.append("---")
        parts.append(original_body)
        parts.append(raw_marker)
        return "\n\n".join(parts)

    @staticmethod
    def format_tracking_marker(tracking_id: str) -> str:
        """Format a tracking ID as a marker string."""
        return TRACKING_ID_FORMAT.format(tracking_id=tracking_id)
