import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.plugins.sdk import TimestampMixin, UUIDPrimaryKeyMixin

from ..config import NOTE_MAX_LENGTH
from .base import EcommerceBase

REASON_MAX_LENGTH = 30


class StockLevel(EcommerceBase, TimestampMixin):
    __tablename__ = "plg_ecommerce_stock_levels"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plg_ecommerce_products.id", ondelete="CASCADE"), primary_key=True
    )
    business_id: Mapped[uuid.UUID]
    quantity: Mapped[int] = mapped_column(default=0)
    low_stock_threshold: Mapped[int | None] = mapped_column(default=None)


class StockMovement(EcommerceBase, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plg_ecommerce_stock_movements"

    business_id: Mapped[uuid.UUID]
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plg_ecommerce_products.id", ondelete="CASCADE")
    )
    change: Mapped[int]
    quantity_after: Mapped[int]
    reason: Mapped[str] = mapped_column(String(REASON_MAX_LENGTH))
    order_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    note: Mapped[str | None] = mapped_column(String(NOTE_MAX_LENGTH), default=None)
    created_by: Mapped[uuid.UUID | None] = mapped_column(default=None)
