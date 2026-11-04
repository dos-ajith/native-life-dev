from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Product, StockLevel, StockMovement


@dataclass(frozen=True)
class StockRow:
    product_id: UUID
    product_name: str
    sku: str
    quantity: int
    low_stock_threshold: int | None


class InventoryRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def lock_stock(self, business_id: UUID, product_ids: list[UUID]) -> dict[UUID, StockLevel]:
        rows = self._db.scalars(
            select(StockLevel)
            .where(StockLevel.business_id == business_id, StockLevel.product_id.in_(product_ids))
            .order_by(StockLevel.product_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return {row.product_id: row for row in rows}

    def get_stock(self, business_id: UUID, product_id: UUID) -> StockLevel | None:
        return self._db.scalar(
            select(StockLevel)
            .where(StockLevel.business_id == business_id, StockLevel.product_id == product_id)
            .execution_options(populate_existing=True)
        )

    def add_stock(self, stock: StockLevel) -> StockLevel:
        self._db.add(stock)
        self._db.flush()
        return stock

    def add_movement(self, movement: StockMovement) -> StockMovement:
        self._db.add(movement)
        self._db.flush()
        return movement

    def list_stock(
        self,
        business_id: UUID,
        default_threshold: int,
        low_only: bool,
        offset: int,
        limit: int,
    ) -> tuple[list[StockRow], int]:
        threshold = func.coalesce(StockLevel.low_stock_threshold, default_threshold)
        filters = [StockLevel.business_id == business_id]
        if low_only:
            filters.append(StockLevel.quantity <= threshold)
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(StockLevel)
                .join(Product, Product.id == StockLevel.product_id)
                .where(*filters)
            )
            or 0
        )
        rows = self._db.execute(
            select(
                StockLevel.product_id,
                Product.name,
                Product.sku,
                StockLevel.quantity,
                StockLevel.low_stock_threshold,
            )
            .join(Product, Product.id == StockLevel.product_id)
            .where(*filters)
            .order_by(StockLevel.quantity, Product.name, Product.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return [StockRow(*row) for row in rows], total

    def list_movements(
        self, business_id: UUID, product_id: UUID | None, offset: int, limit: int
    ) -> tuple[list[StockMovement], int]:
        filters = [StockMovement.business_id == business_id]
        if product_id is not None:
            filters.append(StockMovement.product_id == product_id)
        total = (
            self._db.scalar(select(func.count()).select_from(StockMovement).where(*filters)) or 0
        )
        items = self._db.scalars(
            select(StockMovement)
            .where(*filters)
            .order_by(StockMovement.created_at.desc(), StockMovement.id)
            .offset(offset)
            .limit(limit)
        ).all()
        return list(items), total
