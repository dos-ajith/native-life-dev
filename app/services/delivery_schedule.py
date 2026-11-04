from datetime import date, datetime, timedelta

from app.models.delivery_settings import DeliverySettings

DAYS_IN_WEEK = 7


def is_within_working_hours(settings: DeliverySettings, now: datetime) -> bool:
    return (
        now.isoweekday() in settings.working_days
        and settings.route_start_time <= now.time() <= settings.route_end_time
    )


def next_working_day(settings: DeliverySettings, today: date) -> date:
    for offset in range(1, DAYS_IN_WEEK + 1):
        candidate = today + timedelta(days=offset)
        if candidate.isoweekday() in settings.working_days:
            return candidate
    return today + timedelta(days=1)
