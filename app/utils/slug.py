import re

_NON_SLUG_CHARS = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    return _NON_SLUG_CHARS.sub("-", value.strip().lower()).strip("-")
