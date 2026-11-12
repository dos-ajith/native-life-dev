from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.product_cart_item import ProductCartItem


class ProductCartRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find(self, user_id: UUID, business_id: UUID, product_id: UUID) -> ProductCartItem | None:
        return self._db.scalar(
            select(ProductCartItem).where(
                ProductCartItem.user_id == user_id,
                ProductCartItem.business_id == business_id,
                ProductCartItem.product_id == product_id,
            )
        )

    def get_owned(self, line_id: UUID, user_id: UUID) -> ProductCartItem | None:
        return self._db.scalar(
            select(ProductCartItem).where(
                ProductCartItem.id == line_id, ProductCartItem.user_id == user_id
            )
        )

    def list_for_user(self, user_id: UUID) -> list[ProductCartItem]:
        return list(
            self._db.scalars(
                select(ProductCartItem)
                .where(ProductCartItem.user_id == user_id)
                .order_by(ProductCartItem.created_at, ProductCartItem.id)
            )
        )

    def add(self, line: ProductCartItem) -> ProductCartItem:
        self._db.add(line)
        self._db.flush()
        return line

    def delete(self, line: ProductCartItem) -> None:
        self._db.delete(line)
        self._db.flush()

    def remove_for_business(self, user_id: UUID, business_id: UUID) -> int:
        result = self._db.execute(
            delete(ProductCartItem)
            .where(ProductCartItem.user_id == user_id, ProductCartItem.business_id == business_id)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount)  # type: ignore[attr-defined]
