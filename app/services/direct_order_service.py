from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError, NotFoundError
from app.core.messages import DealMessages, OrderMessages
from app.models.order import DeliveryOption, Order, OrderItem, OrderStatus, OrderType
from app.models.user import User
from app.models.user_address import UserAddress
from app.plugins.deal_commerce import DealProduct, StockLine
from app.plugins.registry import PluginRegistry
from app.repositories.order_repository import OrderRepository
from app.schemas.direct_order import DirectOrderCreate
from app.schemas.order import OrderRead
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService
from app.services.deal_commerce_resolver import DealCommerceResolver
from app.services.deal_expiry_service import deal_clock_now
from app.services.delivery_plan_service import (
    DeliveryPlanService,
    DeliveryTarget,
    expected_delivery_fields,
)
from app.services.delivery_request_service import DeliveryRequestService
from app.services.order_numbers import new_order_number
from app.services.user_address_service import UserAddressService, format_shipping_address

ENTITY_TYPE = "order"


def _ordered_products(
    payload: DirectOrderCreate, products: dict[UUID, DealProduct]
) -> list[tuple[DealProduct, int]]:
    product_ids = [line.product_id for line in payload.items]
    if len(set(product_ids)) != len(product_ids):
        raise BusinessRuleError(OrderMessages.PRODUCTS_DUPLICATED)
    ordered: list[tuple[DealProduct, int]] = []
    for line in payload.items:
        product = products.get(line.product_id)
        if product is None:
            raise NotFoundError(DealMessages.PRODUCT_NOT_FOUND)
        if not product.is_active:
            raise BusinessRuleError(DealMessages.PRODUCT_INACTIVE.format(name=product.name))
        ordered.append((product, line.quantity))
    return ordered


def _new_order_item(product: DealProduct, quantity: int) -> OrderItem:
    return OrderItem(
        product_id=product.id,
        product_name=product.name,
        unit_price=product.selling_price,
        quantity=quantity,
        line_total=product.selling_price * quantity,
    )


class DirectOrderService:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._db = db
        self._orders = OrderRepository(db)
        self._businesses = BusinessService(db)
        self._resolver = DealCommerceResolver(db, registry)
        self._addresses = UserAddressService(db)
        self._plans = DeliveryPlanService(db)
        self._delivery_requests = DeliveryRequestService(db)
        self._activity_logs = ActivityLogService(db)

    def place(self, business_id: UUID, payload: DirectOrderCreate, actor: User) -> OrderRead:
        self._businesses.get_active(business_id)
        provider = self._resolver.provider_for(business_id)
        address = self._address(payload.address_id, actor)
        plan = self._plans.plan(
            payload.delivery_option,
            DeliveryTarget.from_address(address) if address is not None else None,
            payload.route_id,
            None,
            deal_clock_now(),
        )
        shipped_to = address if plan.option != DeliveryOption.SELF_PICKUP else None
        ordered = _ordered_products(
            payload,
            provider.find_products(
                self._db, business_id, [line.product_id for line in payload.items]
            ),
        )
        order = self._orders.add(
            Order(
                order_number=new_order_number(self._db),
                order_type=OrderType.DIRECT,
                business_id=business_id,
                customer_id=actor.id,
                promoter_id=plan.promoter_id,
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
                currency=provider.currency(self._db, business_id),
                total_amount=Decimal(0),
                items=[_new_order_item(product, quantity) for product, quantity in ordered],
            )
        )
        order.total_amount = sum((item.line_total for item in order.items), Decimal(0)) + plan.fee
        provider.reserve_stock(
            self._db,
            business_id,
            order.id,
            [StockLine(product_id=product.id, quantity=quantity) for product, quantity in ordered],
            actor.id,
        )
        request = self._delivery_requests.create(order, plan)
        self._commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ORDER_PLACED,
            entity_type=ENTITY_TYPE,
            entity_id=order.id,
            metadata={
                "order_number": order.order_number,
                "item_count": len(order.items),
                "total_amount": str(order.total_amount),
                "delivery_option": plan.option.value,
            },
        )
        self._delivery_requests.announce(request, plan, order, actor)
        return OrderRead.from_order(order)

    def _address(self, address_id: UUID | None, actor: User) -> UserAddress | None:
        if address_id is None:
            return None
        return self._addresses.get_owned(address_id, actor)

    def _commit(self) -> None:
        try:
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(OrderMessages.CONFLICT) from exc
