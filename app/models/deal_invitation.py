import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DealInvitationStatus(enum.StrEnum):
    INVITED = "invited"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CLOSED = "closed"


class DealInvitation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deal_invitations"
    __table_args__ = (
        UniqueConstraint("deal_id", "user_id", name="uq_deal_invitations_deal_id_user_id"),
        Index("ix_deal_invitations_user_id_status", "user_id", "status"),
    )

    deal_id: Mapped[UUID] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"))
    status: Mapped[DealInvitationStatus] = mapped_column(
        Enum(
            DealInvitationStatus,
            name="deal_invitation_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DealInvitationStatus.INVITED,
    )
    notified_at: Mapped[datetime | None] = mapped_column(default=None)
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
