APP_DATE_FORMAT_SETTING_KEY = "app_date_format"
APP_TIME_FORMAT_SETTING_KEY = "app_time_format"

DEFAULT_APP_DATE_FORMAT = "DD-MM-YYYY"
DEFAULT_APP_TIME_FORMAT = "hh:mm A"

_date_format = DEFAULT_APP_DATE_FORMAT
_time_format = DEFAULT_APP_TIME_FORMAT


def set_datetime_formats(date_format: str | None, time_format: str | None) -> None:
    global _date_format, _time_format
    _date_format = date_format or DEFAULT_APP_DATE_FORMAT
    _time_format = time_format or DEFAULT_APP_TIME_FORMAT


def get_datetime_formats() -> tuple[str, str]:
    return _date_format, _time_format
