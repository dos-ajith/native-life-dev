import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.business import Business
from app.models.category import Category

if TYPE_CHECKING:
    from app.models.deal_image import DealImage
    from app.models.deal_item import DealItem
    from app.models.deal_native import DealNative
    from app.models.user import User

DEALS_ROOT_CATEGORY_NAME = "Deals"


class DealStatus(enum.StrEnum):
    DRAFT = "draft"
    PENDING_ACCEPTANCE = "pending_acceptance"
    PUBLISHED = "published"
    BLOCKED = "blocked"
    PENDING_OWNER_APPROVAL = "pending_owner_approval"
    CLOSED = "closed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Deal(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "deals"
    __table_args__ = (
        CheckConstraint("max_acceptances >= 1", name="ck_deals_max_acceptances_positive"),
        CheckConstraint(
            "accepted_count >= 0 AND accepted_count <= max_acceptances",
            name="ck_deals_accepted_count_within_max",
        ),
        Index("ix_deals_created_by", "created_by"),
        Index("ix_deals_business_id", "business_id"),
        Index("ix_deals_category_id", "category_id"),
        Index(
            "ix_deals_published_at",
            "published_at",
            postgresql_where=text("status = 'published' AND deleted_at IS NULL"),
        ),
        Index(
            "ix_deals_acceptance_deadline",
            "acceptance_deadline",
            postgresql_where=text("status = 'pending_acceptance'"),
        ),
    )

    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE")
    )
    category_id: Mapped[UUID] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())
    status: Mapped[DealStatus] = mapped_column(
        Enum(
            DealStatus,
            name="deal_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DealStatus.DRAFT,
    )
    max_acceptances: Mapped[int] = mapped_column(
        SmallInteger(), server_default=text("1"), default=1
    )
    accepted_count: Mapped[int] = mapped_column(SmallInteger(), server_default=text("0"), default=0)
    min_joiners: Mapped[int | None] = mapped_column(Integer(), default=None)
    joined_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    pickup_location: Mapped[str | None] = mapped_column(String(500), default=None)
    delivery_details: Mapped[str | None] = mapped_column(Text(), default=None)
    delivery_options: Mapped[list[str]] = mapped_column(
        ARRAY(String(20)),
        server_default=text("ARRAY['instant','route','self_pickup']::varchar[]"),
    )
    starts_at: Mapped[datetime | None] = mapped_column(default=None)
    valid_until: Mapped[datetime | None] = mapped_column(default=None)
    submitted_at: Mapped[datetime | None] = mapped_column(default=None)
    acceptance_deadline: Mapped[datetime | None] = mapped_column(default=None)
    published_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    business: Mapped[Business | None] = relationship()
    category: Mapped[Category] = relationship()
    natives: Mapped[list["DealNative"]] = relationship(
        cascade="all, delete-orphan", order_by="DealNative.created_at"
    )
    items: Mapped[list["DealItem"]] = relationship(
        cascade="all, delete-orphan", order_by="[DealItem.sort_order, DealItem.created_at]"
    )
    images: Mapped[list["DealImage"]] = relationship(
        cascade="all, delete-orphan", order_by="[DealImage.sort_order, DealImage.created_at]"
    )
