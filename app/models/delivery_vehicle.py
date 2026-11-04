import enum
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

VEHICLE_NAME_LENGTH = 100


class VehicleType(enum.StrEnum):
    BICYCLE = "bicycle"
    BIKE = "bike"
    AUTO = "auto"
    VAN = "van"
    TRUCK = "truck"


class DeliveryVehicle(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "delivery_vehicles"
    __table_args__ = (Index("ix_delivery_vehicles_user_id", "user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    vehicle_type: Mapped[VehicleType] = mapped_column(
        Enum(
            VehicleType,
            name="vehicle_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    name: Mapped[str] = mapped_column(String(VEHICLE_NAME_LENGTH))
    is_active: Mapped[bool] = mapped_column(default=True)
