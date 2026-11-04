from uuid import UUID

from app.plugins.sdk import BusinessRuleError

from ..config import MAX_STOCK_QUANTITY
from ..messages import EcommerceMessages
from ..models import StockLevel, StockMovement
from ..repositories.inventory_repository import InventoryRepository
from ..stock_rules import StockReason


class StockLedger:
    def __init__(self, inventory: InventoryRepository) -> None:
        self._inventory = inventory

    @staticmethod
    def ensure_change_allowed(stock: StockLevel, product_name: str, change: int) -> None:
        new_quantity = stock.quantity + change
        if new_quantity < 0:
            raise BusinessRuleError(
                EcommerceMessages.INSUFFICIENT_STOCK.format(
                    name=product_name, available=stock.quantity, requested=-change
                )
            )
        if new_quantity > MAX_STOCK_QUANTITY:
            raise BusinessRuleError(
                EcommerceMessages.STOCK_LIMIT_EXCEEDED.format(limit=MAX_STOCK_QUANTITY)
            )

    def apply(
        self,
        stock: StockLevel,
        product_name: str,
        change: int,
        reason: StockReason,
        actor_id: UUID | None,
        order_id: UUID | None = None,
        note: str | None = None,
    ) -> StockMovement:
        self.ensure_change_allowed(stock, product_name, change)
        stock.quantity += change
        return self._inventory.add_movement(
            StockMovement(
                business_id=stock.business_id,
                product_id=stock.product_id,
                change=change,
                quantity_after=stock.quantity,
                reason=reason.value,
                order_id=order_id,
                note=note,
                created_by=actor_id,
            )
        )
