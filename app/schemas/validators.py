from typing import Annotated

from pydantic import AfterValidator


def _require_non_blank(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


NonBlankStr = Annotated[str, AfterValidator(_require_non_blank)]
