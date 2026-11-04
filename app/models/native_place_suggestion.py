import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.gis_district import GisDistrict
    from app.models.user import User


class NativePlaceSuggestionStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class NativePlaceSuggestion(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "native_place_suggestions"

    name: Mapped[str] = mapped_column(String(150))
    district_id: Mapped[UUID] = mapped_column(ForeignKey("gis_districts.id", ondelete="RESTRICT"))
    status: Mapped[NativePlaceSuggestionStatus] = mapped_column(
        Enum(
            NativePlaceSuggestionStatus,
            name="native_place_suggestion_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=NativePlaceSuggestionStatus.PENDING,
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review_note: Mapped[str | None] = mapped_column(Text())

    district: Mapped["GisDistrict"] = relationship()
    submitter: Mapped["User | None"] = relationship(foreign_keys=[created_by])
