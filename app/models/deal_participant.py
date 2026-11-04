from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class DealParticipant(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deal_participants"
    __table_args__ = (
        UniqueConstraint("deal_id", "user_id", name="uq_deal_participants_deal_id_user_id"),
        Index("ix_deal_participants_user_id", "user_id"),
    )

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship()
