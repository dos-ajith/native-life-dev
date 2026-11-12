from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import CartMessages, DealMessages
from app.models.product_cart_item import ProductCartItem
from app.models.user import User
from app.plugins.deal_commerce import DealProduct
from app.plugins.registry import PluginRegistry
from app.repositories.business_repository import BusinessRepository
from app.repositories.product_cart_repository import ProductCartRepository
from app.schemas.cart import (
    CartBusinessGroupRead,
    CartItemUpdate,
    CartProductAdd,
    CartProductItemRead,
)
from app.schemas.deal_order import MAX_ORDER_LINE_QUANTITY, OrderDetails
from app.schemas.direct_order import DirectOrderCreate, DirectOrderLineCreate
from app.schemas.order import OrderRead
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.deal_commerce_resolver import DealCommerceResolver
from app.services.direct_order_service import DirectOrderService

ENTITY_TYPE = "product_cart_item"
BUSINESS_ENTITY_TYPE = "business"


class ProductCartService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._registry = registry
        self._lines = ProductCartRepository(db)
        self._business_repository = BusinessRepository(db)
        self._businesses = BusinessService(db)
        self._resolver = DealCommerceResolver(db, registry)
        self._activity_logs = ActivityLogService(db)

    def groups(self, actor: User) -> tuple[list[CartBusinessGroupRead], int]:
        lines = self._lines.list_for_user(actor.id)
        by_business: dict[UUID, list[ProductCartItem]] = {}
        for line in lines:
            by_business.setdefault(line.business_id, []).append(line)
        groups = [
            group
            for business_id, business_lines in by_business.items()
            if (group := self._group(business_id, business_lines)) is not None
        ]
        return groups, sum(line.quantity for line in lines)

    def add(self, payload: CartProductAdd, actor: User) -> None:
        self._businesses.get_active(payload.business_id)
        provider = self._resolver.provider_for(payload.business_id)
        product = provider.find_products(self._db, payload.business_id, [payload.product_id]).get(
            payload.product_id
        )
        if product is None:
            raise NotFoundError(DealMessages.PRODUCT_NOT_FOUND)
        if not product.is_active:
            raise BusinessRuleError(DealMessages.PRODUCT_INACTIVE.format(name=product.name))
        existing = self._lines.find(actor.id, payload.business_id, payload.product_id)
        quantity = payload.quantity + (existing.quantity if existing else 0)
        _ensure_quantity_allowed(quantity)
        if existing is None:
            line = self._lines.add(
                ProductCartItem(
                    user_id=actor.id,
                    business_id=payload.business_id,
                    product_id=payload.product_id,
                    quantity=quantity,
                )
            )
            action = ActivityAction.PRODUCT_CART_ITEM_ADDED
        else:
            existing.quantity = quantity
            line = existing
            action = ActivityAction.PRODUCT_CART_ITEM_UPDATED
        self._commit()
        self._log(actor, action, line)

    def update(self, line_id: UUID, payload: CartItemUpdate, actor: User) -> None:
        line = self._owned(line_id, actor)
        line.quantity = payload.quantity
        self._commit()
        self._log(actor, ActivityAction.PRODUCT_CART_ITEM_UPDATED, line)

    def remove(self, line_id: UUID, actor: User) -> None:
        line = self._owned(line_id, actor)
        metadata = _log_metadata(line)
        self._lines.delete(line)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.PRODUCT_CART_ITEM_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=line_id,
            metadata=metadata,
        )

    def remove_business(self, business_id: UUID, actor: User) -> None:
        removed = self._lines.remove_for_business(actor.id, business_id)
        if removed == 0:
            raise NotFoundError(CartMessages.BUSINESS_NOT_IN_CART)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.PRODUCT_CART_BUSINESS_REMOVED,
            entity_type=BUSINESS_ENTITY_TYPE,
            entity_id=business_id,
            metadata={"removed_lines": removed},
        )

    def checkout_business(self, business_id: UUID, details: OrderDetails, actor: User) -> OrderRead:
        return self._checkout(details, actor, business_id)[0]

    def checkout_all(self, details: OrderDetails, actor: User) -> list[OrderRead]:
        return self._checkout(details, actor, None)

    def _checkout(
        self, details: OrderDetails, actor: User, business_id: UUID | None
    ) -> list[OrderRead]:
        lines = [
            line
            for line in self._lines.list_for_user(actor.id)
            if business_id is None or line.business_id == business_id
        ]
        if not lines:
            raise BusinessRuleError(CartMessages.NOTHING_TO_CHECK_OUT_BUSINESS)
        by_business: dict[UUID, list[ProductCartItem]] = {}
        for line in lines:
            by_business.setdefault(line.business_id, []).append(line)
        entries = [
            (
                owner_id,
                DirectOrderCreate(
                    **details.model_dump(),
                    items=[
                        DirectOrderLineCreate(product_id=line.product_id, quantity=line.quantity)
                        for line in business_lines
                    ],
                ),
            )
            for owner_id, business_lines in by_business.items()
        ]
        placed = DirectOrderService(self._db, self._registry).place_many(entries, actor)
        for owner_id in by_business:
            self._lines.remove_for_business(actor.id, owner_id)
        self._commit()
        return placed

    def _group(
        self, business_id: UUID, lines: list[ProductCartItem]
    ) -> CartBusinessGroupRead | None:
        business = self._business_repository.get_by_id(business_id)
        if business is None:
            return None
        products = self._products_for(business_id, [line.product_id for line in lines])
        items = [
            CartProductItemRead.from_line(line, products.get(line.product_id)) for line in lines
        ]
        subtotal = sum((item.line_total or Decimal(0) for item in items), Decimal(0))
        tax_total = sum((item.tax_amount for item in items), Decimal(0))
        return CartBusinessGroupRead(
            business_id=business_id,
            business_name=business.name,
            items=items,
            subtotal=subtotal,
            tax_total=tax_total,
            total=subtotal + tax_total,
        )

    def _products_for(self, business_id: UUID, product_ids: list[UUID]) -> dict[UUID, DealProduct]:
        try:
            provider = self._resolver.provider_for(business_id)
        except BusinessRuleError:
            return {}
        return provider.find_products(self._db, business_id, product_ids)

    def _owned(self, line_id: UUID, actor: User) -> ProductCartItem:
        line = self._lines.get_owned(line_id, actor.id)
        if line is None:
            raise NotFoundError(CartMessages.PRODUCT_LINE_NOT_FOUND)
        return line

    def _commit(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(CartMessages.CONFLICT) from exc

    def _log(self, actor: User, action: str, line: ProductCartItem) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=line.id,
            metadata=_log_metadata(line),
        )


def _log_metadata(line: ProductCartItem) -> dict[str, str | int]:
    return {
        "business_id": str(line.business_id),
        "product_id": str(line.product_id),
        "quantity": line.quantity,
    }


def _ensure_quantity_allowed(quantity: int) -> None:
    if quantity > MAX_ORDER_LINE_QUANTITY:
        raise BusinessRuleError(
            CartMessages.QUANTITY_TOO_HIGH.format(limit=MAX_ORDER_LINE_QUANTITY)
        )
