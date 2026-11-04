from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.cart_item import CartItem
from app.models.deal_item import DealItem


class CartRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_deal_item(self, deal_item_id: UUID) -> DealItem | None:
        return self._db.get(DealItem, deal_item_id)

    def find(self, user_id: UUID, deal_item_id: UUID) -> CartItem | None:
        return self._db.scalar(
            select(CartItem).where(
                CartItem.user_id == user_id, CartItem.deal_item_id == deal_item_id
            )
        )

    def get_owned(self, cart_item_id: UUID, user_id: UUID) -> CartItem | None:
        return self._db.scalar(
            select(CartItem).where(CartItem.id == cart_item_id, CartItem.user_id == user_id)
        )

    def list_for_user(self, user_id: UUID) -> list[CartItem]:
        return list(
            self._db.scalars(
                select(CartItem)
                .where(CartItem.user_id == user_id)
                .order_by(CartItem.created_at, CartItem.id)
            )
        )

    def add(self, cart_item: CartItem) -> CartItem:
        self._db.add(cart_item)
        self._db.flush()
        return cart_item

    def delete(self, cart_item: CartItem) -> None:
        self._db.delete(cart_item)
        self._db.flush()

    def remove_deal_items(self, user_id: UUID, deal_item_ids: Sequence[UUID]) -> None:
        self._db.execute(
            delete(CartItem)
            .where(CartItem.user_id == user_id, CartItem.deal_item_id.in_(deal_item_ids))
            .execution_options(synchronize_session=False)
        )

    def remove_for_deal(self, user_id: UUID, deal_id: UUID) -> int:
        result = self._db.execute(
            delete(CartItem)
            .where(
                CartItem.user_id == user_id,
                CartItem.deal_item_id.in_(select(DealItem.id).where(DealItem.deal_id == deal_id)),
            )
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
