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
    ) -> str:
        """Build delegation email body with tracking marker appended."""
        marker = TRACKING_ID_FORMAT.format(tracking_id=tracking_id)
        return f"{original_body}\n\n{marker}"

    @staticmethod
    def format_tracking_marker(tracking_id: str) -> str:
        """Format a tracking ID as a marker string."""
        return TRACKING_ID_FORMAT.format(tracking_id=tracking_id)
