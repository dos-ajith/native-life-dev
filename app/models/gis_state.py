from typing import TYPE_CHECKING, Any

from geoalchemy2 import Geometry
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.gis_district import GisDistrict


class GisState(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "gis_states"

    lgd_code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
    )

    districts: Mapped[list["GisDistrict"]] = relationship(back_populates="state")
