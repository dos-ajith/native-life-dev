from collections.abc import Collection
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.models.chat_conversation import ChatConversation
from app.models.direct_message import DirectMessage


class DirectMessageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, message: DirectMessage) -> DirectMessage:
        self._db.add(message)
        self._db.flush()
        self._db.execute(
            update(ChatConversation)
            .where(ChatConversation.id == message.conversation_id)
            .values(last_message_at=func.now())
        )
        self._db.commit()
        self._db.refresh(message)
        return message

    def get_in_conversation(self, conversation_id: UUID, message_id: UUID) -> DirectMessage | None:
        return self._db.scalar(
            select(DirectMessage).where(
                DirectMessage.id == message_id, DirectMessage.conversation_id == conversation_id
            )
        )

    def list_older(
        self, conversation_id: UUID, before: DirectMessage | None, limit: int
    ) -> list[DirectMessage]:
        query = select(DirectMessage).where(DirectMessage.conversation_id == conversation_id)
        if before is not None:
            query = query.where(
                or_(
                    DirectMessage.created_at < before.created_at,
                    and_(
                        DirectMessage.created_at == before.created_at,
                        DirectMessage.id < before.id,
                    ),
                )
            )
        newest_first = DirectMessage.created_at.desc(), DirectMessage.id.desc()
        return list(self._db.scalars(query.order_by(*newest_first).limit(limit)))

    def latest_by_conversation(
        self, conversation_ids: Collection[UUID]
    ) -> dict[UUID, DirectMessage]:
        if not conversation_ids:
            return {}
        rows = self._db.scalars(
            select(DirectMessage)
            .ext(distinct_on(DirectMessage.conversation_id))
            .where(DirectMessage.conversation_id.in_(conversation_ids))
            .order_by(
                DirectMessage.conversation_id,
                DirectMessage.created_at.desc(),
                DirectMessage.id.desc(),
            )
        )
        return {message.conversation_id: message for message in rows}

    def unread_counts(self, conversation_ids: Collection[UUID], reader_id: UUID) -> dict[UUID, int]:
        if not conversation_ids:
            return {}
        rows = self._db.execute(
            select(DirectMessage.conversation_id, func.count())
            .where(
                DirectMessage.conversation_id.in_(conversation_ids),
                DirectMessage.sender_id != reader_id,
                DirectMessage.read_at.is_(None),
            )
            .group_by(DirectMessage.conversation_id)
        ).all()
        return {conversation_id: count for conversation_id, count in rows}

    def mark_read(self, conversation_id: UUID, reader_id: UUID) -> int:
        marked_ids = self._db.scalars(
            update(DirectMessage)
            .where(
                DirectMessage.conversation_id == conversation_id,
                DirectMessage.sender_id != reader_id,
                DirectMessage.read_at.is_(None),
            )
            .values(read_at=func.now())
            .returning(DirectMessage.id)
        ).all()
        self._db.commit()
        return len(marked_ids)
