from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from app.plugins.sdk import DealCommerceProvider, DealProduct, StockLine

from .repositories.product_repository import ProductRepository
from .services.deal_stock_service import DealStockService
from .services.settings_service import SettingsService


class EcommerceDealCommerce(DealCommerceProvider):
    def find_products(
        self, db: Session, business_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, DealProduct]:
        return {
            product.id: DealProduct(
                id=product.id,
                name=product.name,
                description=product.description,
                unit=None,
                selling_price=product.selling_price,
                is_active=product.is_active,
            )
            for product in ProductRepository(db).get_many(business_id, list(product_ids))
        }

    def currency(self, db: Session, business_id: UUID) -> str:
        currency, _ = SettingsService(db).effective(business_id)
        return currency

    def reserve_stock(
        self,
        db: Session,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None:
        DealStockService(db).reserve(business_id, order_id, lines, actor_id)

    def release_stock(
        self,
        db: Session,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None:
        DealStockService(db).release(business_id, order_id, lines, actor_id)
