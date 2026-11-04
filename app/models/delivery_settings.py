from datetime import time
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ForeignKey, Numeric, SmallInteger, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

FEE_PRECISION = 12
FEE_SCALE = 2


class DeliverySettings(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "delivery_settings"
    __table_args__ = (UniqueConstraint("user_id", name="uq_delivery_settings_user_id"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    working_days: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger()))
    route_start_time: Mapped[time]
    route_end_time: Mapped[time]
    instant_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(FEE_PRECISION, FEE_SCALE), default=None
    )
    route_fee: Mapped[Decimal | None] = mapped_column(
        Numeric(FEE_PRECISION, FEE_SCALE), default=None
    )
