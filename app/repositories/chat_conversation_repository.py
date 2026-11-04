from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.chat_conversation import ChatConversation
from app.schemas.pagination import PaginationParams


def _ordered(first_id: UUID, second_id: UUID) -> tuple[UUID, UUID]:
    return (first_id, second_id) if first_id < second_id else (second_id, first_id)


class ChatConversationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_between(self, first_id: UUID, second_id: UUID) -> ChatConversation | None:
        lower_id, higher_id = _ordered(first_id, second_id)
        return self._db.scalar(
            select(ChatConversation).where(
                ChatConversation.lower_user_id == lower_id,
                ChatConversation.higher_user_id == higher_id,
            )
        )

    def get_or_create(self, first_id: UUID, second_id: UUID) -> ChatConversation:
        lower_id, higher_id = _ordered(first_id, second_id)
        self._db.execute(
            insert(ChatConversation)
            .values(lower_user_id=lower_id, higher_user_id=higher_id)
            .on_conflict_do_nothing(constraint="uq_chat_conversations_lower_user_id_higher")
        )
        self._db.commit()
        conversation = self.get_between(first_id, second_id)
        assert conversation is not None
        return conversation

    def list_partner_ids(self, user_id: UUID) -> list[UUID]:
        rows = self._db.execute(
            select(ChatConversation.lower_user_id, ChatConversation.higher_user_id).where(
                or_(
                    ChatConversation.lower_user_id == user_id,
                    ChatConversation.higher_user_id == user_id,
                )
            )
        ).all()
        return [higher if lower == user_id else lower for lower, higher in rows]

    def list_for_user(
        self, user_id: UUID, params: PaginationParams
    ) -> tuple[list[ChatConversation], int]:
        condition = (
            or_(
                ChatConversation.lower_user_id == user_id,
                ChatConversation.higher_user_id == user_id,
            ),
            ChatConversation.last_message_at.is_not(None),
        )
        total = (
            self._db.scalar(select(func.count()).select_from(ChatConversation).where(*condition))
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(ChatConversation)
            .where(*condition)
            .order_by(ChatConversation.last_message_at.desc(), ChatConversation.id.desc())
            .offset(offset)
            .limit(params.page_size)
        )
        return list(items), total
