from typing import Annotated

from pydantic import AfterValidator


def _require_non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def _require_name(value: str) -> str:
    stripped = _require_non_blank(value)
    if any(char.isdigit() for char in stripped):
        raise ValueError("must not contain numbers")
    if not any(char.isalpha() for char in stripped):
        raise ValueError("must contain at least one letter")
    return stripped


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
NameStr = Annotated[str, AfterValidator(_require_name)]
