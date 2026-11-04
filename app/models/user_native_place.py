import enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.gis_village import GisVillage


class NativePlaceSlot(enum.StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class UserNativePlace(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_native_places"
    __table_args__ = (
        UniqueConstraint("user_id", "slot", name="uq_user_native_places_user_id_slot"),
        UniqueConstraint("user_id", "village_id", name="uq_user_native_places_user_id_village_id"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    village_id: Mapped[UUID] = mapped_column(ForeignKey("gis_villages.id", ondelete="RESTRICT"))
    slot: Mapped[NativePlaceSlot] = mapped_column(
        Enum(
            NativePlaceSlot,
            name="native_place_slot",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )

    village: Mapped["GisVillage"] = relationship()
