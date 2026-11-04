import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import Enum, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.category import Category

if TYPE_CHECKING:
    from app.models.user import User


class BusinessStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class BusinessVerificationStatus(enum.StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Business(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "businesses"
    __table_args__ = (
        Index("ix_businesses_owner_id", "owner_id"),
        Index("ix_businesses_category_id", "category_id"),
    )

    owner_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    category_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text())
    location: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    status: Mapped[BusinessStatus] = mapped_column(
        Enum(
            BusinessStatus,
            name="business_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=BusinessStatus.ACTIVE,
    )
    verification_status: Mapped[BusinessVerificationStatus] = mapped_column(
        Enum(
            BusinessVerificationStatus,
            name="business_verification_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=BusinessVerificationStatus.PENDING,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review_note: Mapped[str | None] = mapped_column(Text(), default=None)
    resubmission_count: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    escalated_at: Mapped[datetime | None] = mapped_column(default=None)
    escalated_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    escalation_note: Mapped[str | None] = mapped_column(Text(), default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    category: Mapped[Category | None] = relationship()

    @property
    def latitude(self) -> float | None:
        return to_shape(self.location).y if self.location is not None else None

    @property
    def longitude(self) -> float | None:
        return to_shape(self.location).x if self.location is not None else None
