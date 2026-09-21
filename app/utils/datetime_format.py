import re
from datetime import date, datetime, time

_TOKEN_TO_STRFTIME = {
    "YYYY": "%Y",
    "YY": "%y",
    "MM": "%m",
    "DD": "%d",
    "HH": "%H",
    "hh": "%I",
    "mm": "%M",
    "ss": "%S",
    "A": "%p",
}

_TOKEN_PATTERN = re.compile("|".join(sorted(_TOKEN_TO_STRFTIME, key=len, reverse=True)))


def _to_strftime(token_format: str) -> str:
    return _TOKEN_PATTERN.sub(lambda match: _TOKEN_TO_STRFTIME[match.group()], token_format)


def format_date(value: date, date_format: str) -> str:
    return value.strftime(_to_strftime(date_format))


def format_time(value: time, time_format: str) -> str:
    return value.strftime(_to_strftime(time_format))


def format_datetime(value: datetime, date_format: str, time_format: str) -> str:
    return value.strftime(_to_strftime(f"{date_format} {time_format}"))
