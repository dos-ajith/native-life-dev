from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_district import GisDistrict


class GisTaluk(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "gis_taluks"

    district_id: Mapped[UUID] = mapped_column(ForeignKey("gis_districts.id", ondelete="CASCADE"))
    lgd_code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
    )

    district: Mapped[GisDistrict] = relationship(back_populates="taluks")
