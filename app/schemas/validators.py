from datetime import date
from typing import Annotated

from pydantic import AfterValidator

from app.core.messages import ValidationMessages
from app.core.timezone import app_now
from app.utils.phone import normalize_mobile_number


def _require_non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(ValidationMessages.NAME_BLANK)
    return stripped


def _require_name(value: str) -> str:
    stripped = _require_non_blank(value)
    if any(char.isdigit() for char in stripped):
        raise ValueError(ValidationMessages.NAME_CONTAINS_NUMBERS)
    if not any(char.isalpha() for char in stripped):
        raise ValueError(ValidationMessages.NAME_MISSING_LETTER)
    return stripped


def _require_not_numeric_only(value: str) -> str:
    stripped = _require_non_blank(value)
    if not any(char.isalpha() for char in stripped):
        raise ValueError(ValidationMessages.NAME_NUMERIC_ONLY)
    return stripped


def _require_mobile_number(value: str) -> str:
    normalized = normalize_mobile_number(value)
    if normalized is None:
        raise ValueError(ValidationMessages.INVALID_PHONE)
    return normalized


def _require_true(value: bool) -> bool:
    if not value:
        raise ValueError(ValidationMessages.TERMS_NOT_ACCEPTED)
    return value


def _require_not_future(value: date) -> date:
    if value > app_now().date():
        raise ValueError(ValidationMessages.DATE_OF_BIRTH_IN_FUTURE)
    return value


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
MobileNumberStr = Annotated[str, AfterValidator(_require_mobile_number)]
AcceptedBool = Annotated[bool, AfterValidator(_require_true)]
NameStr = Annotated[str, AfterValidator(_require_name)]
AlphanumericStr = Annotated[str, AfterValidator(_require_not_numeric_only)]
PastDate = Annotated[date, AfterValidator(_require_not_future)]
