from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.deal_item import DealItem


class CartItem(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cart_items"
    __table_args__ = (
        UniqueConstraint("user_id", "deal_item_id", name="uq_cart_items_user_id_deal_item_id"),
        CheckConstraint("quantity > 0", name="ck_cart_items_quantity_positive"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    deal_item_id: Mapped[UUID] = mapped_column(ForeignKey("deal_items.id", ondelete="CASCADE"))
    quantity: Mapped[int] = mapped_column(Integer())

    deal_item: Mapped[DealItem] = relationship(lazy="joined")
