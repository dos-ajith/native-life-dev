from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProductCartItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "product_cart_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "business_id",
            "product_id",
            name="uq_product_cart_items_user_id_business_id_product_id",
        ),
        CheckConstraint("quantity > 0", name="ck_product_cart_items_quantity_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    product_id: Mapped[UUID] = mapped_column()
    quantity: Mapped[int] = mapped_column(Integer())
