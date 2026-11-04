from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.timezone import app_now
from app.models.notification import Notification, NotificationType
from app.schemas.pagination import PaginationParams


class NotificationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, notification: Notification) -> Notification:
        self._db.add(notification)
        self._db.commit()
        self._db.refresh(notification)
        return notification

    def exists_from_actor(
        self,
        recipient_id: UUID,
        actor_id: UUID,
        entity_id: UUID,
        types: Sequence[NotificationType],
    ) -> bool:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.recipient_id == recipient_id,
                    Notification.actor_id == actor_id,
                    Notification.entity_id == entity_id,
                    Notification.type.in_(types),
                )
            )
            or 0
        ) > 0

    def list_recipient_ids_for_entity(
        self, entity_id: UUID, types: Sequence[NotificationType]
    ) -> list[UUID]:
        return list(
            self._db.scalars(
                select(Notification.recipient_id)
                .where(Notification.entity_id == entity_id, Notification.type.in_(types))
                .distinct()
            )
        )

    def list_actor_ids_for_entity(
        self, entity_id: UUID, types: Sequence[NotificationType]
    ) -> list[UUID]:
        return list(
            self._db.scalars(
                select(Notification.actor_id)
                .where(
                    Notification.entity_id == entity_id,
                    Notification.type.in_(types),
                    Notification.actor_id.is_not(None),
                )
                .distinct()
            )
        )

    def get_by_id_for_recipient(
        self, notification_id: UUID, recipient_id: UUID
    ) -> Notification | None:
        return self._db.scalar(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )

    def list_for_recipient(
        self, recipient_id: UUID, params: PaginationParams, unread_only: bool
    ) -> tuple[list[Notification], int]:
        conditions = [Notification.recipient_id == recipient_id]
        if unread_only:
            conditions.append(Notification.is_read.is_(False))

        total = (
            self._db.scalar(select(func.count()).select_from(Notification).where(*conditions)) or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def count_unread(self, recipient_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.recipient_id == recipient_id,
                    Notification.is_read.is_(False),
                )
            )
            or 0
        )

    def mark_read(self, notification: Notification) -> Notification:
        if notification.is_read:
            return notification
        notification.is_read = True
        notification.read_at = app_now()
        self._db.commit()
        self._db.refresh(notification)
        return notification

    def mark_all_read(self, recipient_id: UUID) -> int:
        updated_ids = self._db.scalars(
            update(Notification)
            .where(
                Notification.recipient_id == recipient_id,
                Notification.is_read.is_(False),
            )
            .values(is_read=True, read_at=func.now())
            .returning(Notification.id)
        ).all()
        self._db.commit()
        return len(updated_ids)
