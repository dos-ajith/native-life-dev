from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import get_settings
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import DealMessages, OrderMessages
from app.models.deal import Deal
from app.models.deal_item import DealItem
from app.models.order import (
    DeliveryOption,
    Order,
    OrderItem,
    OrderStatus,
    OrderType,
)
from app.models.user import User
from app.models.user_address import UserAddress
from app.plugins.deal_commerce import DealCommerceProvider, DealProduct, StockLine
from app.plugins.registry import PluginRegistry
from app.repositories.cart_repository import CartRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.deal_order import DealOrderCreate, DealOrderLineCreate
from app.schemas.order import OrderRead
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_availability import ensure_deal_open
from app.services.deal_commerce_resolver import DealCommerceResolver
from app.services.deal_delivery_service import DealDeliveryService
from app.services.deal_expiry_service import DealExpiryService, deal_clock_now
from app.services.delivery_plan_service import DeliveryTarget, expected_delivery_fields
from app.services.delivery_request_service import DeliveryRequestService
from app.services.order_numbers import new_order_number
from app.services.user_address_service import UserAddressService, format_shipping_address

ENTITY_TYPE = "deal"


@dataclass(frozen=True)
class OrderLine:
    item: DealItem
    product_id: UUID | None
    quantity: int


def _order_lines(deal: Deal, requested: list[DealOrderLineCreate]) -> list[OrderLine]:
    requested_ids = [line.deal_item_id for line in requested]
    if len(set(requested_ids)) != len(requested_ids):
        raise BusinessRuleError(DealMessages.ORDER_ITEMS_DUPLICATED)
    items = {item.id: item for item in deal.items}
    lines: list[OrderLine] = []
    for line in requested:
        item = items.get(line.deal_item_id)
        if item is None:
            raise NotFoundError(DealMessages.ITEM_NOT_FOUND)
        if item.deal_price is None or (deal.business_id is not None and item.product_id is None):
            raise BusinessRuleError(DealMessages.ORDER_ITEM_NOT_ORDERABLE.format(name=item.name))
        lines.append(OrderLine(item=item, product_id=item.product_id, quantity=line.quantity))
    return lines


def _ensure_products_orderable(lines: list[OrderLine], products: dict[UUID, DealProduct]) -> None:
    for line in lines:
        product = products.get(line.product_id) if line.product_id is not None else None
        if product is None:
            raise NotFoundError(DealMessages.PRODUCT_NOT_FOUND)
        if not product.is_active:
            raise BusinessRuleError(DealMessages.PRODUCT_INACTIVE.format(name=product.name))
        if line.item.deal_price is not None and line.item.deal_price > product.selling_price:
            raise BusinessRuleError(DealMessages.PRODUCT_PRICE_CHANGED.format(name=product.name))


def _new_order_item(line: OrderLine) -> OrderItem:
    unit_price = line.item.deal_price or Decimal(0)
    return OrderItem(
        deal_item_id=line.item.id,
        product_id=line.product_id,
        product_name=line.item.name,
        unit_price=unit_price,
        quantity=line.quantity,
        line_total=unit_price * line.quantity,
    )


def _currency(provider: DealCommerceProvider | None, db: Session, business_id: UUID | None) -> str:
    if provider is None or business_id is None:
        return get_settings().default_currency
    return provider.currency(db, business_id)


class DealOrderService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._orders = OrderRepository(db)
        self._participants = DealParticipantRepository(db)
        self._carts = CartRepository(db)
        self._delivery = DealDeliveryService(db)
        self._delivery_requests = DeliveryRequestService(db)
        self._access = DealAccessPolicy(db)
        self._expiry = DealExpiryService(db)
        self._businesses = BusinessService(db)
        self._resolver = DealCommerceResolver(db, registry)
        self._addresses = UserAddressService(db)
        self._activity_logs = ActivityLogService(db)

    def place(self, deal_id: UUID, payload: DealOrderCreate, actor: User) -> OrderRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, actor)
        if not self._participants.exists(deal.id, actor.id):
            raise BusinessRuleError(DealMessages.JOIN_REQUIRED)
        ensure_deal_open(deal)
        business_id = deal.business_id
        provider = self._provider_for(business_id)
        address = self._address(payload.address_id, actor)
        plan = self._delivery.quote(
            deal,
            payload.delivery_option,
            DeliveryTarget.from_address(address) if address is not None else None,
            payload.route_id,
            deal_clock_now(),
        )
        shipped_to = address if plan.option != DeliveryOption.SELF_PICKUP else None
        lines = _order_lines(deal, payload.items)
        if business_id is not None and provider is not None:
            _ensure_products_orderable(
                lines,
                provider.find_products(
                    self._db, business_id, [line.product_id for line in lines if line.product_id]
                ),
            )
        self._orders.lock_deal_items([line.item.id for line in lines])
        self._ensure_within_deal_limits(lines)
        order = self._orders.add(
            Order(
                order_number=new_order_number(self._db),
                order_type=OrderType.DEAL,
                deal_id=deal.id,
                business_id=business_id,
                customer_id=actor.id,
                promoter_id=self._delivery.accepted_promoter_id(deal),
                delivery_option=plan.option,
                delivery_fee=plan.fee,
                payment_method=payload.payment_method,
                **expected_delivery_fields(plan),
                status=OrderStatus.PENDING,
                customer_name=payload.customer_name,
                customer_phone=payload.customer_phone,
                shipping_address=format_shipping_address(shipped_to) if shipped_to else None,
                shipping_location=shipped_to.location if shipped_to else None,
                shipping_village_id=shipped_to.village_id if shipped_to else None,
                shipping_address_id=shipped_to.id if shipped_to else None,
                notes=payload.notes,
                currency=_currency(provider, self._db, business_id),
                total_amount=Decimal(0),
                items=[_new_order_item(line) for line in lines],
            )
        )
        order.total_amount = sum((item.line_total for item in order.items), Decimal(0)) + plan.fee
        if business_id is not None and provider is not None:
            provider.reserve_stock(
                self._db,
                business_id,
                order.id,
                [
                    StockLine(product_id=line.product_id, quantity=line.quantity)
                    for line in lines
                    if line.product_id is not None
                ],
                actor.id,
            )
        self._carts.remove_deal_items(actor.id, [line.item.id for line in lines])
        request = self._delivery_requests.create(order, plan)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DEAL_ORDER_PLACED,
            entity_type=ENTITY_TYPE,
            entity_id=deal.id,
            metadata={
                "order_id": str(order.id),
                "order_number": order.order_number,
                "item_count": len(order.items),
                "total_amount": str(order.total_amount),
                "delivery_option": plan.option.value,
            },
        )
        self._delivery_requests.announce(request, plan, order, actor)
        return OrderRead.from_order(order)

    def _provider_for(self, business_id: UUID | None) -> DealCommerceProvider | None:
        if business_id is None:
            return None
        self._businesses.get_active(business_id)
        return self._resolver.provider_for(business_id)

    def _address(self, address_id: UUID | None, actor: User) -> UserAddress | None:
        if address_id is None:
            return None
        return self._addresses.get_owned(address_id, actor)

    def _ensure_within_deal_limits(self, lines: list[OrderLine]) -> None:
        for line in lines:
            limit = line.item.quantity
            if limit is None:
                continue
            ordered = self._orders.deal_item_ordered_quantity(line.item.id)
            if ordered + line.quantity > limit:
                raise BusinessRuleError(
                    DealMessages.ORDER_ITEM_LIMIT_EXCEEDED.format(
                        remaining=max(limit - ordered, 0), name=line.item.name
                    )
                )

    def _commit(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(OrderMessages.CONFLICT) from exc
