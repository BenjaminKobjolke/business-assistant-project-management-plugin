"""Email-task tracking service."""

from __future__ import annotations

import re
import uuid

from .constants import TRACKING_ID_FORMAT, TRACKING_ID_PATTERN
from .database import PmDatabase, PmTracking


class TrackingService:
    """CRUD operations for email-task tracking records."""

    def __init__(self, db: PmDatabase) -> None:
        self._db = db

    @staticmethod
    def generate_tracking_id() -> str:
        """Generate a new UUID v4 tracking ID."""
        return str(uuid.uuid4())

    @staticmethod
    def format_tracking_marker(tracking_id: str) -> str:
        """Format a tracking ID as a marker string."""
        return TRACKING_ID_FORMAT.format(tracking_id=tracking_id)

    @staticmethod
    def extract_tracking_id(text: str) -> str | None:
        """Extract a tracking ID from text using regex."""
        match = re.search(TRACKING_ID_PATTERN, text)
        if match:
            return match.group(1)
        return None

    def create_tracking(
        self,
        email_id: str,
        email_folder: str,
        email_subject: str = "",
        email_from: str = "",
        task_name: str = "",
        rtm_task_id: str | None = None,
        delegated_to: str | None = None,
        project_name: str | None = None,
    ) -> str:
        """Create a tracking record and return the tracking ID."""
        tracking_id = self.generate_tracking_id()
        self._db.create_tracking(
            tracking_id=tracking_id,
            email_id=email_id,
            email_folder=email_folder,
            email_subject=email_subject,
            email_from=email_from,
            task_name=task_name,
            rtm_task_id=rtm_task_id,
            delegated_to=delegated_to,
            project_name=project_name,
        )
        return tracking_id

    def find_by_tracking_id(self, tracking_id: str) -> PmTracking | None:
        """Find a tracking record by tracking ID."""
        return self._db.find_tracking_by_id(tracking_id)

    def find_by_rtm_task_id(self, rtm_task_id: str) -> PmTracking | None:
        """Find a tracking record by RTM task ID."""
        return self._db.find_tracking_by_rtm_task_id(rtm_task_id)

    def complete_tracking(self, tracking_id: str) -> bool:
        """Mark a tracking record as completed."""
        return self._db.complete_tracking(tracking_id)

    def list_active(self, delegated_to: str = "") -> list[PmTracking]:
        """List active tracking records, optionally filtered by delegate."""
        return self._db.list_tracking(status="active", delegated_to=delegated_to)
