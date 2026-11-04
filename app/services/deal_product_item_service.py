from collections.abc import Collection
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DealMessages
from app.models.deal import Deal
from app.models.deal_item import DealItem
from app.plugins.deal_commerce import DealProduct
from app.plugins.registry import PluginRegistry
from app.schemas.deal import DealItemCreate
from app.services.deal_commerce_resolver import DealCommerceResolver


def _ensure_sellable(product: DealProduct | None, deal_price: Decimal | None) -> DealProduct:
    if product is None:
        raise NotFoundError(DealMessages.PRODUCT_NOT_FOUND)
    if not product.is_active:
        raise BusinessRuleError(DealMessages.PRODUCT_INACTIVE.format(name=product.name))
    if deal_price is not None and deal_price > product.selling_price:
        raise BusinessRuleError(DealMessages.PRODUCT_PRICE_CHANGED.format(name=product.name))
    return product


class DealProductItemService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._resolver = DealCommerceResolver(db, registry)

    def build_items(
        self,
        business_id: UUID | None,
        payloads: list[DealItemCreate],
        first_position: int = 0,
        taken_product_ids: Collection[UUID] = (),
    ) -> list[DealItem]:
        product_ids = [payload.product_id for payload in payloads if payload.product_id]
        if business_id is None:
            if product_ids:
                raise BusinessRuleError(DealMessages.PRODUCT_ITEMS_NEED_BUSINESS)
            return [
                DealItem(sort_order=first_position + offset, **payload.model_dump())
                for offset, payload in enumerate(payloads)
            ]
        if len(product_ids) != len(payloads):
            raise BusinessRuleError(DealMessages.ITEMS_MUST_BE_PRODUCTS)
        if len(set(product_ids)) != len(product_ids) or not set(product_ids).isdisjoint(
            taken_product_ids
        ):
            raise BusinessRuleError(DealMessages.PRODUCT_DUPLICATED)
        products = self._resolver.provider_for(business_id).find_products(
            self._db, business_id, product_ids
        )
        return [
            self._product_item(payload, products, first_position + offset)
            for offset, payload in enumerate(payloads)
        ]

    def ensure_ready(self, deal: Deal) -> None:
        if deal.business_id is None:
            return
        if any(item.product_id is None for item in deal.items):
            raise BusinessRuleError(DealMessages.ITEMS_MUST_BE_PRODUCTS)
        products = self._resolver.provider_for(deal.business_id).find_products(
            self._db, deal.business_id, [item.product_id for item in deal.items if item.product_id]
        )
        for item in deal.items:
            _ensure_sellable(
                products.get(item.product_id) if item.product_id else None, item.deal_price
            )

    @staticmethod
    def _product_item(
        payload: DealItemCreate, products: dict[UUID, DealProduct], position: int
    ) -> DealItem:
        product = _ensure_sellable(
            products.get(payload.product_id) if payload.product_id else None, payload.deal_price
        )
        return DealItem(
            sort_order=position,
            product_id=product.id,
            name=product.name,
            description=payload.description or product.description,
            unit=product.unit,
            quantity=payload.quantity,
            original_price=product.selling_price,
            deal_price=payload.deal_price,
            image_id=payload.image_id,
        )
