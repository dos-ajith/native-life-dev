from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import CartMessages, DealMessages
from app.models.cart_item import CartItem
from app.models.deal import Deal
from app.models.deal_item import DealItem
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.repositories.cart_repository import CartRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
from app.schemas.cart import (
    CartCheckout,
    CartDealGroupRead,
    CartItemAdd,
    CartItemUpdate,
    CartProductAdd,
    CartRead,
)
from app.schemas.deal_order import (
    MAX_ORDER_LINE_QUANTITY,
    DealOrderCreate,
    DealOrderLineCreate,
    OrderDetails,
)
from app.schemas.order import OrderRead
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import get_deal
from app.services.deal_availability import ensure_deal_open
from app.services.deal_order_service import DealOrderService
from app.services.product_cart_service import ProductCartService

ENTITY_TYPE = "cart_item"
DEAL_ENTITY_TYPE = "deal"


class CartService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._carts = CartRepository(db)
        self._deals = DealRepository(db)
        self._participants = DealParticipantRepository(db)
        self._orders = DealOrderService(db, registry)
        self._products = ProductCartService(db, registry)
        self._activity_logs = ActivityLogService(db)

    def get(self, actor: User) -> CartRead:
        lines = self._carts.list_for_user(actor.id)
        deals = self._deals.get_by_ids(list({line.deal_item.deal_id for line in lines}))
        groups: dict[UUID, list[CartItem]] = {}
        for line in lines:
            groups.setdefault(line.deal_item.deal_id, []).append(line)
        businesses, product_quantity = self._products.groups(actor)
        return CartRead(
            deals=[
                CartDealGroupRead.from_lines(deals[deal_id], group)
                for deal_id, group in groups.items()
                if deal_id in deals
            ],
            businesses=businesses,
            total_quantity=sum(line.quantity for line in lines) + product_quantity,
        )

    def add_product(self, payload: CartProductAdd, actor: User) -> CartRead:
        self._products.add(payload, actor)
        return self.get(actor)

    def update_product(self, cart_item_id: UUID, payload: CartItemUpdate, actor: User) -> CartRead:
        self._products.update(cart_item_id, payload, actor)
        return self.get(actor)

    def remove_product(self, cart_item_id: UUID, actor: User) -> CartRead:
        self._products.remove(cart_item_id, actor)
        return self.get(actor)

    def remove_business(self, business_id: UUID, actor: User) -> CartRead:
        self._products.remove_business(business_id, actor)
        return self.get(actor)

    def checkout_business(self, business_id: UUID, details: OrderDetails, actor: User) -> OrderRead:
        return self._products.checkout_business(business_id, details, actor)

    def checkout_all_businesses(self, details: OrderDetails, actor: User) -> list[OrderRead]:
        return self._products.checkout_all(details, actor)

    def add_item(self, payload: CartItemAdd, actor: User) -> CartRead:
        item = self._carts.get_deal_item(payload.deal_item_id)
        if item is None:
            raise NotFoundError(DealMessages.ITEM_NOT_FOUND)
        deal = get_deal(self._deals, item.deal_id)
        self._ensure_joined(deal, actor)
        ensure_deal_open(deal)
        if item.deal_price is None or (deal.business_id is not None and item.product_id is None):
            raise BusinessRuleError(DealMessages.ORDER_ITEM_NOT_ORDERABLE.format(name=item.name))
        existing = self._carts.find(actor.id, item.id)
        quantity = payload.quantity + (existing.quantity if existing else 0)
        _ensure_quantity_allowed(quantity)
        _ensure_quantity_available(item, quantity)
        if existing is None:
            line = self._carts.add(
                CartItem(user_id=actor.id, deal_item_id=item.id, quantity=quantity)
            )
            action = ActivityAction.CART_ITEM_ADDED
        else:
            existing.quantity = quantity
            line = existing
            action = ActivityAction.CART_ITEM_UPDATED
        self._commit()
        self._log(actor, action, line)
        return self.get(actor)

    def update_item(self, cart_item_id: UUID, payload: CartItemUpdate, actor: User) -> CartRead:
        line = self._owned(cart_item_id, actor)
        _ensure_quantity_available(line.deal_item, payload.quantity)
        line.quantity = payload.quantity
        self._commit()
        self._log(actor, ActivityAction.CART_ITEM_UPDATED, line)
        return self.get(actor)

    def remove_item(self, cart_item_id: UUID, actor: User) -> CartRead:
        line = self._owned(cart_item_id, actor)
        metadata = _log_metadata(line)
        self._carts.delete(line)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.CART_ITEM_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=cart_item_id,
            metadata=metadata,
        )
        return self.get(actor)

    def remove_deal(self, deal_id: UUID, actor: User) -> CartRead:
        removed = self._carts.remove_for_deal(actor.id, deal_id)
        if removed == 0:
            raise NotFoundError(CartMessages.DEAL_NOT_IN_CART)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.CART_DEAL_REMOVED,
            entity_type=DEAL_ENTITY_TYPE,
            entity_id=deal_id,
            metadata={"removed_lines": removed},
        )
        return self.get(actor)

    def checkout(self, payload: CartCheckout, actor: User) -> OrderRead:
        lines = [
            line
            for line in self._carts.list_for_user(actor.id)
            if line.deal_item.deal_id == payload.deal_id
        ]
        if not lines:
            raise BusinessRuleError(CartMessages.NOTHING_TO_CHECK_OUT)
        order = DealOrderCreate(
            **payload.model_dump(exclude={"deal_id"}),
            items=[
                DealOrderLineCreate(deal_item_id=line.deal_item_id, quantity=line.quantity)
                for line in lines
            ],
        )
        return self._orders.place(payload.deal_id, order, actor)

    def _ensure_joined(self, deal: Deal, actor: User) -> None:
        if not self._participants.exists(deal.id, actor.id):
            raise BusinessRuleError(DealMessages.JOIN_REQUIRED)

    def _owned(self, cart_item_id: UUID, actor: User) -> CartItem:
        line = self._carts.get_owned(cart_item_id, actor.id)
        if line is None:
            raise NotFoundError(CartMessages.ITEM_NOT_FOUND)
        return line

    def _commit(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(CartMessages.CONFLICT) from exc

    def _log(self, actor: User, action: str, line: CartItem) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=line.id,
            metadata=_log_metadata(line),
        )


def _log_metadata(line: CartItem) -> dict[str, str | int]:
    return {"deal_item_id": str(line.deal_item_id), "quantity": line.quantity}


def _ensure_quantity_allowed(quantity: int) -> None:
    if quantity > MAX_ORDER_LINE_QUANTITY:
        raise BusinessRuleError(
            CartMessages.QUANTITY_TOO_HIGH.format(limit=MAX_ORDER_LINE_QUANTITY)
        )


def _ensure_quantity_available(item: DealItem, quantity: int) -> None:
    if item.quantity is None:
        return
    remaining = max(item.quantity - item.ordered_quantity, 0)
    if quantity > remaining:
        raise BusinessRuleError(
            DealMessages.ORDER_ITEM_LIMIT_EXCEEDED.format(remaining=remaining, name=item.name)
        )
