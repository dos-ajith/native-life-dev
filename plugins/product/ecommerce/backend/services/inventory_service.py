from uuid import UUID

from sqlalchemy.orm import Session

from app.plugins.sdk import NotFoundError, Page, PaginationParams, User, record_activity

from ..activity_actions import EcommerceAction, EcommerceEntity
from ..messages import EcommerceMessages
from ..models import Product
from ..repositories.inventory_repository import InventoryRepository
from ..repositories.product_repository import ProductRepository
from ..schemas.inventory import (
    StockAdjustmentCreate,
    StockLevelRead,
    StockMovementRead,
    StockThresholdUpdate,
)
from ..schemas.product import ProductStockRead
from ..stock_rules import StockReason
from .settings_service import SettingsService
from .stock_ledger import StockLedger


class InventoryService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._products = ProductRepository(db)
        self._inventory = InventoryRepository(db)
        self._ledger = StockLedger(self._inventory)
        self._settings = SettingsService(db)

    def get_stock(self, business_id: UUID, product_id: UUID) -> ProductStockRead:
        self._ensure_product(business_id, product_id)
        stock = self._inventory.get_stock(business_id, product_id)
        if stock is None:
            raise NotFoundError(EcommerceMessages.STOCK_NOT_FOUND)
        return ProductStockRead.model_validate(stock)

    def list_stock(
        self, business_id: UUID, params: PaginationParams, low_only: bool
    ) -> Page[StockLevelRead]:
        _, default_threshold = self._settings.effective(business_id)
        rows, total = self._inventory.list_stock(
            business_id,
            default_threshold,
            low_only,
            (params.page - 1) * params.page_size,
            params.page_size,
        )
        items = [
            StockLevelRead(
                product_id=row.product_id,
                product_name=row.product_name,
                sku=row.sku,
                quantity=row.quantity,
                low_stock_threshold=row.low_stock_threshold,
                effective_low_stock_threshold=_effective(
                    row.low_stock_threshold, default_threshold
                ),
                is_low_stock=row.quantity <= _effective(row.low_stock_threshold, default_threshold),
            )
            for row in rows
        ]
        return Page[StockLevelRead].create(items, total, params)

    def adjust(
        self, business_id: UUID, product_id: UUID, payload: StockAdjustmentCreate, actor: User
    ) -> ProductStockRead:
        product = self._ensure_product(business_id, product_id)
        stock = self._inventory.lock_stock(business_id, [product_id]).get(product_id)
        if stock is None:
            raise NotFoundError(EcommerceMessages.STOCK_NOT_FOUND)
        movement = self._ledger.apply(
            stock,
            product.name,
            payload.change,
            StockReason(payload.reason.value),
            actor.id,
            note=payload.note,
        )
        self._db.commit()
        record_activity(
            self._db,
            actor,
            EcommerceAction.STOCK_ADJUSTED,
            EcommerceEntity.STOCK,
            product_id,
            {
                "business_id": str(business_id),
                "reason": movement.reason,
                "change": movement.change,
                "quantity_after": movement.quantity_after,
            },
        )
        return self.get_stock(business_id, product_id)

    def set_threshold(
        self, business_id: UUID, product_id: UUID, payload: StockThresholdUpdate, actor: User
    ) -> ProductStockRead:
        self._ensure_product(business_id, product_id)
        stock = self._inventory.lock_stock(business_id, [product_id]).get(product_id)
        if stock is None:
            raise NotFoundError(EcommerceMessages.STOCK_NOT_FOUND)
        stock.low_stock_threshold = payload.low_stock_threshold
        self._db.commit()
        record_activity(
            self._db,
            actor,
            EcommerceAction.LOW_STOCK_THRESHOLD_UPDATED,
            EcommerceEntity.STOCK,
            product_id,
            {"business_id": str(business_id), "low_stock_threshold": payload.low_stock_threshold},
        )
        return self.get_stock(business_id, product_id)

    def movements(
        self, business_id: UUID, product_id: UUID | None, params: PaginationParams
    ) -> Page[StockMovementRead]:
        if product_id is not None:
            self._ensure_product(business_id, product_id)
        items, total = self._inventory.list_movements(
            business_id,
            product_id,
            (params.page - 1) * params.page_size,
            params.page_size,
        )
        return Page[StockMovementRead].create(
            [StockMovementRead.model_validate(item) for item in items], total, params
        )

    def _ensure_product(self, business_id: UUID, product_id: UUID) -> Product:
        product = self._products.get(business_id, product_id)
        if product is None:
            raise NotFoundError(EcommerceMessages.PRODUCT_NOT_FOUND)
        return product


def _effective(threshold: int | None, default_threshold: int) -> int:
    return default_threshold if threshold is None else threshold
