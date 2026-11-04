import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.plugins.sdk import TimestampMixin

from ..config import CURRENCY_LENGTH
from .base import EcommerceBase


class EcommerceSettings(EcommerceBase, TimestampMixin):
    __tablename__ = "plg_ecommerce_settings"

    business_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(CURRENCY_LENGTH))
    default_low_stock_threshold: Mapped[int]
