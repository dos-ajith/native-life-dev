import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import Settings


def get_app_timezone(settings: Settings) -> ZoneInfo:
    try:
        return ZoneInfo(settings.default_timezone)
    except (ZoneInfoNotFoundError, ValueError):
        pass
    try:
        return ZoneInfo(os.environ.get("TZ", "UTC"))
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def app_now_utc(settings: Settings) -> datetime:
    return datetime.now(get_app_timezone(settings)).astimezone(UTC)
