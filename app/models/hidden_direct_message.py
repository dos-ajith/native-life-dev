from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class HiddenDirectMessage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "hidden_direct_messages"
    __table_args__ = (
        UniqueConstraint(
            "message_id", "user_id", name="uq_hidden_direct_messages_message_id_user_id"
        ),
    )

    message_id: Mapped[UUID] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
