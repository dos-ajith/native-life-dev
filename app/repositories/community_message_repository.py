from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, literal, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.community_message import CommunityMessage
from app.schemas.community_timeline import TimelineItemType

_WITH_REPLY = (
    joinedload(CommunityMessage.sender),
    joinedload(CommunityMessage.reply_to).joinedload(CommunityMessage.sender),
)


class CommunityMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, message: CommunityMessage) -> CommunityMessage:
        self._db.add(message)
        self._db.commit()
        self._db.refresh(message)
        return message

    def get_in_community(self, community_id: UUID, message_id: UUID) -> CommunityMessage | None:
        return self._db.scalar(
            select(CommunityMessage)
            .options(*_WITH_REPLY)
            .where(
                CommunityMessage.id == message_id,
                CommunityMessage.community_id == community_id,
            )
        )

    def timeline_entries(self, community_id: UUID) -> Select[*tuple[Any, ...]]:
        return select(
            CommunityMessage.id.label("id"),
            CommunityMessage.created_at.label("sort_at"),
            literal(TimelineItemType.MESSAGE.value).label("kind"),
        ).where(CommunityMessage.community_id == community_id)

    def list_by_ids(self, message_ids: Sequence[UUID]) -> list[CommunityMessage]:
        return list(
            self._db.scalars(
                select(CommunityMessage)
                .options(*_WITH_REPLY)
                .where(CommunityMessage.id.in_(message_ids))
            )
        )

    def delete(self, message: CommunityMessage) -> None:
        self._db.delete(message)
        self._db.commit()

    def list_older(
        self, community_id: UUID, before: CommunityMessage | None, limit: int
    ) -> list[CommunityMessage]:
        query = (
            select(CommunityMessage)
            .options(*_WITH_REPLY)
            .where(CommunityMessage.community_id == community_id)
        )
        if before is not None:
            query = query.where(
                or_(
                    CommunityMessage.created_at < before.created_at,
                    and_(
                        CommunityMessage.created_at == before.created_at,
                        CommunityMessage.id < before.id,
                    ),
                )
            )
        newest_first = CommunityMessage.created_at.desc(), CommunityMessage.id.desc()
        return list(self._db.scalars(query.order_by(*newest_first).limit(limit)))
