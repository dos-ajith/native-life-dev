from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.activity_log_service import ActivityLogService


def record_activity(
    db: Session,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: UUID,
    metadata: dict[str, Any] | None = None,
) -> None:
    ActivityLogService(db).log(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=metadata,
    )
