from typing import Any

from pydantic import BeforeValidator


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


BlankAsNone = BeforeValidator(_blank_to_none)
