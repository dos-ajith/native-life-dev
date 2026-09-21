from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository

SENSITIVE_METADATA_KEYS = {
    "password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
}


def _sanitize_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
    if metadata is None:
        return None
    return {
        key: value for key, value in metadata.items() if key.lower() not in SENSITIVE_METADATA_KEYS
    }


class ActivityLogService:
    def __init__(self, db: Session) -> None:
        self._activity_logs = ActivityLogRepository(db)

    def log(
        self,
        actor: User | None,
        action: str,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        description: str | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> ActivityLog:
        activity_log = ActivityLog(
            user_id=actor.id if actor is not None else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            metadata_=_sanitize_metadata(metadata),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return self._activity_logs.add(activity_log)
