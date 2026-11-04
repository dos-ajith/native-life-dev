import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text, false, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.plugins.sdk import TimestampMixin, UUIDPrimaryKeyMixin

from ..config import (
    IMAGE_CONTENT_TYPE_MAX_LENGTH,
    IMAGE_URL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    SKU_MAX_LENGTH,
)
from .base import EcommerceBase

if TYPE_CHECKING:
    from .inventory import StockLevel

CATEGORY_SLUG_MAX_LENGTH = 120
IMAGE_ALT_TEXT_MAX_LENGTH = 200


class ProductCategory(EcommerceBase, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plg_ecommerce_product_categories"

    business_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(CATEGORY_SLUG_MAX_LENGTH))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())


class ProductImage(EcommerceBase, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plg_ecommerce_product_images"

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("plg_ecommerce_products.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(String(IMAGE_URL_MAX_LENGTH))
    alt_text: Mapped[str | None] = mapped_column(String(IMAGE_ALT_TEXT_MAX_LENGTH), default=None)
    sort_order: Mapped[int] = mapped_column(default=0)
    content_type: Mapped[str | None] = mapped_column(
        String(IMAGE_CONTENT_TYPE_MAX_LENGTH), default=None
    )
    size_bytes: Mapped[int | None] = mapped_column(default=None)


class Product(EcommerceBase, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "plg_ecommerce_products"

    business_id: Mapped[uuid.UUID]
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("plg_ecommerce_product_categories.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    sku: Mapped[str] = mapped_column(String(SKU_MAX_LENGTH))
    selling_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    original_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=true())
    is_bulk_promotable: Mapped[bool] = mapped_column(default=False, server_default=false())
    is_individually_promotable: Mapped[bool] = mapped_column(default=False, server_default=false())
    created_by: Mapped[uuid.UUID | None] = mapped_column(default=None)

    category: Mapped[ProductCategory | None] = relationship(lazy="joined")
    images: Mapped[list[ProductImage]] = relationship(
        order_by="ProductImage.sort_order, ProductImage.created_at",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    stock: Mapped["StockLevel | None"] = relationship("StockLevel", lazy="joined", uselist=False)
