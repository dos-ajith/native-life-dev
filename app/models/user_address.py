from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_village import GisVillage

LABEL_LENGTH = 50
FULL_NAME_LENGTH = 150
PHONE_LENGTH = 30
ADDRESS_LINE_LENGTH = 255
LANDMARK_LENGTH = 150
PINCODE_LENGTH = 6


class UserAddress(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_addresses"
    __table_args__ = (Index("ix_user_addresses_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    label: Mapped[str] = mapped_column(String(LABEL_LENGTH))
    full_name: Mapped[str] = mapped_column(String(FULL_NAME_LENGTH))
    phone: Mapped[str] = mapped_column(String(PHONE_LENGTH))
    address_line: Mapped[str] = mapped_column(String(ADDRESS_LINE_LENGTH))
    landmark: Mapped[str | None] = mapped_column(String(LANDMARK_LENGTH), default=None)
    village_id: Mapped[UUID] = mapped_column(ForeignKey("gis_villages.id", ondelete="RESTRICT"))
    location: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    pincode: Mapped[str] = mapped_column(String(PINCODE_LENGTH))
    is_default: Mapped[bool] = mapped_column(default=False)

    village: Mapped[GisVillage] = relationship()

    @property
    def latitude(self) -> float:
        return float(to_shape(self.location).y)

    @property
    def longitude(self) -> float:
        return float(to_shape(self.location).x)
