"""Shared helper functions for PM plugin tools."""

from __future__ import annotations

from business_assistant.agent.deps import Deps
from pydantic_ai import RunContext

from .constants import (
    ERR_SETTING_MISSING,
    PLUGIN_DATA_EMAIL_SERVICE,
    PLUGIN_DATA_OBSIDIAN_SERVICE,
    PLUGIN_DATA_RTM_SERVICE,
)
from .database import PmDatabase


def _get_rtm_service(ctx: RunContext[Deps]):
    """Retrieve RTM service from plugin_data."""
    return ctx.deps.plugin_data.get(PLUGIN_DATA_RTM_SERVICE)


def _get_email_service(ctx: RunContext[Deps]):
    """Retrieve email service from plugin_data."""
    return ctx.deps.plugin_data.get(PLUGIN_DATA_EMAIL_SERVICE)


def _get_obsidian_service(ctx: RunContext[Deps]):
    """Retrieve obsidian service from plugin_data."""
    return ctx.deps.plugin_data.get(PLUGIN_DATA_OBSIDIAN_SERVICE)


def _require_setting(db: PmDatabase, key: str) -> str | None:
    """Get a required setting, return error message if missing."""
    value = db.get_setting(key)
    if not value:
        return ERR_SETTING_MISSING.format(key=key)
    return None


def _get_setting_or_default(db: PmDatabase, key: str, default: str) -> str:
    """Get a setting with a fallback default."""
    return db.get_setting(key) or default
