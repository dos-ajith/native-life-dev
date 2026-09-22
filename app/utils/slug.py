import re
from uuid import UUID

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _NON_SLUG_CHARS.sub("-", value.strip().lower()).strip("-")


def build_unique_slug(base: str | None, unique_id: UUID) -> str:
    prefix = slugify(base) if base else ""
    suffix = unique_id.hex[:8]
    return f"{prefix}-{suffix}" if prefix else suffix
