import enum
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.order import DeliveryOption


class DeliveryRequestStatus(enum.StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


ACTIVE_REQUEST_STATUSES = frozenset(
    {DeliveryRequestStatus.REQUESTED, DeliveryRequestStatus.ACCEPTED}
)


class DeliveryRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "delivery_requests"
    __table_args__ = (
        Index(
            "uq_delivery_requests_one_active_per_order",
            "order_id",
            unique=True,
            postgresql_where=text("status IN ('requested', 'accepted')"),
        ),
        Index("ix_delivery_requests_promoter_id_status", "promoter_id", "status"),
        Index("ix_delivery_requests_route_id_delivery_date", "route_id", "delivery_date"),
    )

    order_id: Mapped[UUID] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    option: Mapped[DeliveryOption] = mapped_column(
        Enum(
            DeliveryOption,
            name="delivery_option",
            native_enum=True,
            create_type=False,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    delivery_date: Mapped[date]
    route_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("delivery_routes.id", ondelete="SET NULL"), default=None
    )
    promoter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    status: Mapped[DeliveryRequestStatus] = mapped_column(
        Enum(
            DeliveryRequestStatus,
            name="delivery_request_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=DeliveryRequestStatus.REQUESTED,
    )
    expires_at: Mapped[datetime]
    decided_at: Mapped[datetime | None] = mapped_column(default=None)
    escalated_at: Mapped[datetime | None] = mapped_column(default=None)
    passed_over_promoter_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
