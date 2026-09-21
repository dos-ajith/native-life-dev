from contextvars import ContextVar

APP_DATE_FORMAT_SETTING_KEY = "app_date_format"
APP_TIME_FORMAT_SETTING_KEY = "app_time_format"

DEFAULT_APP_DATE_FORMAT = "DD-MM-YYYY"
DEFAULT_APP_TIME_FORMAT = "hh:mm A"

_date_format_var: ContextVar[str] = ContextVar("app_date_format", default=DEFAULT_APP_DATE_FORMAT)
_time_format_var: ContextVar[str] = ContextVar("app_time_format", default=DEFAULT_APP_TIME_FORMAT)


def set_datetime_formats(date_format: str, time_format: str) -> None:
    _date_format_var.set(date_format)
    _time_format_var.set(time_format)


def get_datetime_formats() -> tuple[str, str]:
    return _date_format_var.get(), _time_format_var.get()
