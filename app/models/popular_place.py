from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.gis_village import GisVillage


class PopularPlace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "popular_places"

    village_id: Mapped[UUID] = mapped_column(
        ForeignKey("gis_villages.id", ondelete="RESTRICT"), unique=True
    )
    image_url: Mapped[str] = mapped_column(String(2048))
    sort_order: Mapped[int] = mapped_column(Integer(), default=0)
    is_active: Mapped[bool] = mapped_column(Boolean(), default=True)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    village: Mapped["GisVillage"] = relationship()
