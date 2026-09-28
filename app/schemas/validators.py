from typing import Annotated

from pydantic import AfterValidator

from app.core.messages import ValidationMessages


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


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
NameStr = Annotated[str, AfterValidator(_require_name)]
AlphanumericStr = Annotated[str, AfterValidator(_require_not_numeric_only)]
