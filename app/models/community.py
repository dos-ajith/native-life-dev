import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_village import GisVillage

if TYPE_CHECKING:
    from app.models.user import User

MAX_COMMUNITY_RESUBMISSIONS = 2


class CommunityStatus(enum.StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class Community(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "communities"
    __table_args__ = (
        Index("ix_communities_owner_id", "owner_id"),
        Index("ix_communities_status", "status"),
        Index("ix_communities_village_id", "village_id"),
        Index(
            "uq_communities_name_active",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("status <> 'rejected'"),
        ),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    village_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("gis_villages.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text())
    image_url: Mapped[str | None] = mapped_column(String(2048))
    auto_approve_members: Mapped[bool] = mapped_column(
        Boolean(), server_default=text("false"), default=False
    )
    max_members: Mapped[int | None] = mapped_column(Integer())
    members_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    status: Mapped[CommunityStatus] = mapped_column(
        Enum(
            CommunityStatus,
            name="community_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=CommunityStatus.PENDING,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review_note: Mapped[str | None] = mapped_column(Text())
    resubmission_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    village: Mapped[GisVillage | None] = relationship()
