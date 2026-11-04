from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql.elements import ColumnElement

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.delivery_vehicle import DeliveryVehicle
from app.models.gis_village import GisVillage

if TYPE_CHECKING:
    from app.models.user import User

ROUTE_NAME_LENGTH = 100


class DeliveryRoute(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "delivery_routes"
    __table_args__ = (Index("ix_delivery_routes_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    village_id: Mapped[UUID] = mapped_column(ForeignKey("gis_villages.id", ondelete="RESTRICT"))
    vehicle_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("delivery_vehicles.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(ROUTE_NAME_LENGTH))
    start_point: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    end_point: Mapped[Any] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False)
    )
    path: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="LINESTRING", srid=4326, spatial_index=False), default=None
    )
    coverage_radius_m: Mapped[int] = mapped_column(Integer())
    is_active: Mapped[bool] = mapped_column(default=True)
    current_location: Mapped[Any | None] = mapped_column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False), default=None
    )
    location_updated_at: Mapped[datetime | None] = mapped_column(default=None)

    village: Mapped[GisVillage] = relationship()
    promoter: Mapped["User"] = relationship(foreign_keys=[user_id])
    vehicle: Mapped[DeliveryVehicle | None] = relationship()

    @property
    def path_coordinates(self) -> list[tuple[float, float]] | None:
        if self.path is None:
            return None
        return [(float(y), float(x)) for x, y in to_shape(self.path).coords]

    @property
    def current_latitude(self) -> float | None:
        return (
            float(to_shape(self.current_location).y) if self.current_location is not None else None
        )

    @property
    def current_longitude(self) -> float | None:
        return (
            float(to_shape(self.current_location).x) if self.current_location is not None else None
        )

    @property
    def start_latitude(self) -> float:
        return float(to_shape(self.start_point).y)

    @property
    def start_longitude(self) -> float:
        return float(to_shape(self.start_point).x)

    @property
    def end_latitude(self) -> float:
        return float(to_shape(self.end_point).y)

    @property
    def end_longitude(self) -> float:
        return float(to_shape(self.end_point).x)


def coverage_path() -> ColumnElement[Any]:
    return func.coalesce(
        DeliveryRoute.path, func.ST_MakeLine(DeliveryRoute.start_point, DeliveryRoute.end_point)
    )
