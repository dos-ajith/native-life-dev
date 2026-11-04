from sqlalchemy.exc import IntegrityError

from .config import UNIQUE_VIOLATION_SQLSTATE


def is_unique_violation(error: IntegrityError) -> bool:
    return getattr(error.orig, "sqlstate", None) == UNIQUE_VIOLATION_SQLSTATE
