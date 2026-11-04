from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.core.config import get_settings

APP_TIMEZONE_SETTING_KEY = "app_timezone"

_cached_timezone: ZoneInfo | None = None


def _parse_timezone(name: str | None) -> ZoneInfo | None:
    if name is None or not name.strip():
        return None
    try:
        return ZoneInfo(name.strip())
    except (ZoneInfoNotFoundError, ValueError):
        return None


def set_app_timezone(name: str | None) -> None:
    global _cached_timezone
    _cached_timezone = _parse_timezone(name)


def reset_timezone_cache() -> None:
    set_app_timezone(None)


def get_app_timezone() -> ZoneInfo:
    return _cached_timezone or ZoneInfo(get_settings().default_timezone)


def app_now() -> datetime:
    return datetime.now(get_app_timezone())


def to_naive_app_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(get_app_timezone()).replace(tzinfo=None)


def naive_app_now() -> datetime:
    return to_naive_app_time(app_now())
