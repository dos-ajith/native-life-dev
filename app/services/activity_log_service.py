from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog
from app.models.user import User
from app.repositories.activity_log_repository import ActivityLogRepository
from app.schemas.activity_log import ActivityActorRead, ActivityLogQuery, ActivityLogRead
from app.schemas.pagination import PaginationParams

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

    def list(
        self, query: ActivityLogQuery, params: PaginationParams
    ) -> tuple[list[ActivityLogRead], int]:
        rows, total = self._activity_logs.page(query, params)
        return [_to_read(log, actor) for log, actor in rows], total


def _to_read(log: ActivityLog, actor: User | None) -> ActivityLogRead:
    return ActivityLogRead(
        id=log.id,
        actor=_actor_read(actor),
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        description=log.description,
        metadata=log.metadata_,
        ip_address=log.ip_address,
        user_agent=log.user_agent,
        created_at=log.created_at,
    )


def _actor_read(actor: User | None) -> ActivityActorRead | None:
    if actor is None:
        return None
    return ActivityActorRead(
        id=actor.id, name=f"{actor.first_name} {actor.last_name}".strip(), email=actor.email
    )
