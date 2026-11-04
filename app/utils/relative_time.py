from datetime import datetime, timedelta

from app.core.messages import RelativeTimeMessages
from app.core.timezone import app_now, get_app_timezone

SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600
DAYS_PER_WEEK = 7
DAYS_PER_MONTH = 30
DAYS_PER_YEAR = 365
YESTERDAY_DAYS = 1
FIRST_WEEKS_DAY = 7
FIRST_MONTHS_DAY = 30


def _as_app_time(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=get_app_timezone())
    return value


def _count(count: int, singular: str, plural: str) -> str:
    return (singular if count == 1 else plural).format(count=count)


def format_relative_time(value: datetime, now: datetime | None = None) -> str:
    elapsed = (now or app_now()) - _as_app_time(value)
    if elapsed < timedelta(minutes=1):
        return RelativeTimeMessages.JUST_NOW
    seconds = int(elapsed.total_seconds())
    if seconds < SECONDS_PER_HOUR:
        return _count(
            seconds // SECONDS_PER_MINUTE,
            RelativeTimeMessages.MINUTE_AGO,
            RelativeTimeMessages.MINUTES_AGO,
        )
    if elapsed < timedelta(days=1):
        return _count(
            seconds // SECONDS_PER_HOUR,
            RelativeTimeMessages.HOUR_AGO,
            RelativeTimeMessages.HOURS_AGO,
        )
    days = elapsed.days
    if days == YESTERDAY_DAYS:
        return RelativeTimeMessages.YESTERDAY
    if days < FIRST_WEEKS_DAY:
        return RelativeTimeMessages.DAYS_AGO.format(count=days)
    if days < FIRST_MONTHS_DAY:
        return _count(
            days // DAYS_PER_WEEK,
            RelativeTimeMessages.WEEK_AGO,
            RelativeTimeMessages.WEEKS_AGO,
        )
    if days < DAYS_PER_YEAR:
        return _count(
            days // DAYS_PER_MONTH,
            RelativeTimeMessages.MONTH_AGO,
            RelativeTimeMessages.MONTHS_AGO,
        )
    return _count(
        days // DAYS_PER_YEAR,
        RelativeTimeMessages.YEAR_AGO,
        RelativeTimeMessages.YEARS_AGO,
    )
