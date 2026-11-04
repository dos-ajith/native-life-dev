from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.plugins.sdk import NotFoundError, StockLine

from ..messages import EcommerceMessages
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.product_repository import ProductRepository
from ..stock_rules import StockReason
from .stock_ledger import StockLedger


class DealStockService:
    def __init__(self, db: Session) -> None:
        self._products = ProductRepository(db)
        self._inventory = InventoryRepository(db)
        self._ledger = StockLedger(self._inventory)

    def reserve(
        self,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None:
        self._apply(business_id, order_id, lines, actor_id, -1, StockReason.ORDER_CREATED)

    def release(
        self,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None:
        self._apply(business_id, order_id, lines, actor_id, 1, StockReason.ORDER_CANCELLED)

    def _apply(
        self,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
        direction: int,
        reason: StockReason,
    ) -> None:
        product_ids = sorted(line.product_id for line in lines)
        names = {p.id: p.name for p in self._products.get_many(business_id, product_ids)}
        stocks = self._inventory.lock_stock(business_id, product_ids)
        for line in lines:
            stock = stocks.get(line.product_id)
            if stock is None:
                raise NotFoundError(EcommerceMessages.STOCK_NOT_FOUND)
            self._ledger.apply(
                stock,
                names[line.product_id],
                direction * line.quantity,
                reason,
                actor_id,
                order_id=order_id,
            )
