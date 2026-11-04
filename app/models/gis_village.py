from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.gis_taluk import GisTaluk


class GisVillage(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "gis_villages"

    taluk_id: Mapped[UUID] = mapped_column(ForeignKey("gis_taluks.id", ondelete="CASCADE"))
    lgd_code: Mapped[str] = mapped_column(String(10), unique=True)
    name: Mapped[str] = mapped_column(String(150))
    tag_name: Mapped[str | None] = mapped_column(String(150))
    image_url: Mapped[str | None] = mapped_column(String(2048))
    native_admin_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), unique=True
    )
    geom: Mapped[Any] = mapped_column(
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=False)
    )

    taluk: Mapped[GisTaluk] = relationship()
