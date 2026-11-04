import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user import User


class CommunityMemberStatus(enum.StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    BLOCKED = "blocked"


class CommunityMember(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "community_members"
    __table_args__ = (
        UniqueConstraint("community_id", "user_id", name="uq_community_members_community_user"),
        Index("ix_community_members_user_id", "user_id"),
    )

    community_id: Mapped[UUID] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[CommunityMemberStatus] = mapped_column(
        Enum(
            CommunityMemberStatus,
            name="community_member_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=CommunityMemberStatus.PENDING,
    )

    last_read_at: Mapped[datetime | None] = mapped_column(default=None)

    user: Mapped[User] = relationship()
