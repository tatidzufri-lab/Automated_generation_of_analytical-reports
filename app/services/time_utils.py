"""Shared datetime helpers that render timestamps in the user's local timezone.

All user-facing timestamps (report headers, chat message times, humanized artifact
names) should go through these helpers instead of directly formatting UTC values.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings


def _resolve_zone() -> ZoneInfo:
    tz_name = get_settings().timezone
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def now_local() -> datetime:
    """Return the current time as an aware datetime in the configured timezone."""
    return datetime.now(tz=_resolve_zone())


def format_local(fmt: str = "%d.%m.%Y %H:%M", moment: datetime | None = None) -> str:
    """Format a datetime in the local timezone. Defaults to 'dd.mm.YYYY HH:MM'."""
    target = moment.astimezone(_resolve_zone()) if moment else now_local()
    return target.strftime(fmt)


def filename_timestamp() -> str:
    """Compact timestamp used in artifact filenames (local time)."""
    return format_local("%Y%m%d%H%M%S")
