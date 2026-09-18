from typing import TYPE_CHECKING, Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_state import GisState

if TYPE_CHECKING:
    from app.models.gis_taluk import GisTaluk


class GisDistrict(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "gis_districts"

    state_id: Mapped[UUID] = mapped_column(ForeignKey("gis_states.id", ondelete="CASCADE"))
    lgd_code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
    )

    state: Mapped[GisState] = relationship(back_populates="districts")
    taluks: Mapped[list["GisTaluk"]] = relationship(back_populates="district")
