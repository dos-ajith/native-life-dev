from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DeliveryRequestMessages, OrderMessages
from app.models.delivery_request import (
    DeliveryRequest,
    DeliveryRequestStatus,
)
from app.models.delivery_settings import DeliverySettings
from app.models.notification import NotificationType
from app.models.order import DeliveryOption, Order, OrderStatus
from app.models.user import User
from app.realtime.publisher import RealtimePublisher
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.delivery_request_repository import DeliveryRequestRepository
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.repositories.delivery_settings_repository import DeliverySettingsRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.user_repository import UserRepository
from app.schemas.delivery_request import (
    DeliveryRequestAccept,
    DeliveryRequestRead,
    DeliveryReRequest,
    DeliveryStopRead,
    RiderLocationRead,
)
from app.schemas.delivery_route import GeoPoint
from app.services.activity_log_service import ActivityLogService
from app.services.deal_expiry_service import deal_clock_now
from app.services.delivery_plan_service import (
    DeliveryPlan,
    DeliveryPlanService,
    DeliveryTarget,
    expected_delivery_fields,
)
from app.services.delivery_schedule import is_within_working_hours, next_working_day
from app.services.delivery_timeout_service import DeliveryTimeoutService
from app.services.notification_service import NotificationService

ENTITY_TYPE = "delivery_request"
RESCHEDULABLE_ORDER_STATUSES = frozenset({OrderStatus.PENDING, OrderStatus.CONFIRMED})
OPEN_STATUSES = frozenset({DeliveryRequestStatus.REQUESTED})


def _person_name(user: User | None) -> str | None:
    return f"{user.first_name} {user.last_name}" if user is not None else None


def _destination(order: Order) -> GeoPoint | None:
    if order.shipping_latitude is None or order.shipping_longitude is None:
        return None
    return GeoPoint(latitude=order.shipping_latitude, longitude=order.shipping_longitude)


class DeliveryRequestService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._db = db
        self._requests = DeliveryRequestRepository(db)
        self._routes = DeliveryRouteRepository(db)
        self._settings = DeliverySettingsRepository(db)
        self._orders = OrderRepository(db)
        self._users = UserRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._plans = DeliveryPlanService(db)
        self._timeouts = DeliveryTimeoutService(db)
        self._notifications = NotificationService(db, publisher)
        self._activity_logs = ActivityLogService(db)

    def create(self, order: Order, plan: DeliveryPlan) -> DeliveryRequest | None:
        if (
            plan.option == DeliveryOption.SELF_PICKUP
            or plan.delivery_date is None
            or plan.expires_at is None
        ):
            return None
        request = DeliveryRequest(
            order_id=order.id,
            option=plan.option,
            delivery_date=plan.delivery_date,
            route_id=plan.route_id,
            promoter_id=plan.promoter_id,
            expires_at=plan.expires_at,
        )
        if plan.option == DeliveryOption.INSTANT and plan.promoter_id is None:
            now = deal_clock_now()
            request.escalated_at = now
            request.expires_at = now + self._timeouts.claim_window()
        return self._requests.add(request)

    def announce(
        self, request: DeliveryRequest | None, plan: DeliveryPlan, order: Order, actor: User
    ) -> None:
        if request is None:
            return
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_REQUESTED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"order_id": str(order.id), "option": request.option.value},
        )
        for promoter_id in plan.notify_promoter_ids:
            self._notifications.notify_delivery(
                promoter_id,
                actor.id,
                NotificationType.DELIVERY_REQUESTED,
                request.id,
                order.order_number,
            )

    def cancel_for_order(self, order_id: UUID) -> None:
        for request in self._requests.list_active_for_order(order_id):
            request.status = DeliveryRequestStatus.CANCELLED
            request.decided_at = deal_clock_now()

    def expire_overdue(self) -> int:
        overdue = self._requests.list_overdue(deal_clock_now())
        expired: list[tuple[UUID, UUID, str]] = []
        escalated: list[tuple[UUID, str, tuple[UUID, ...]]] = []
        for request in overdue:
            order = self._orders.get(request.order_id)
            if order is not None and request.escalated_at is None:
                candidates = self._escalate(request, order)
                if candidates is not None:
                    escalated.append((request.id, order.order_number, candidates))
                    continue
            request.status = DeliveryRequestStatus.EXPIRED
            request.decided_at = deal_clock_now()
            if order is not None:
                expired.append((request.id, order.customer_id, order.order_number))
        self._db.commit()
        for request_id, order_number, candidates in escalated:
            self._announce_escalation(request_id, order_number, candidates)
        for request_id, customer_id, order_number in expired:
            self._activity_logs.log(
                actor=None,
                action=ActivityAction.DELIVERY_EXPIRED,
                entity_type=ENTITY_TYPE,
                entity_id=request_id,
            )
            self._notifications.notify_delivery(
                customer_id, None, NotificationType.DELIVERY_EXPIRED, request_id, order_number
            )
        return len(overdue)

    def list_for_promoter(
        self, status: DeliveryRequestStatus, actor: User
    ) -> list[DeliveryRequestRead]:
        self.expire_overdue()
        requests = self._requests.list_for_promoter(actor.id, {status})
        return [self._read(request) for request in requests]

    def get_for_order(self, order_id: UUID, actor: User) -> DeliveryRequestRead:
        self.expire_overdue()
        order = self._own_order(order_id, actor)
        request = self._requests.latest_for_order(order.id)
        if request is None:
            raise NotFoundError(DeliveryRequestMessages.NO_DELIVERY)
        return self._read(request, with_rider=True)

    def accept(
        self, request_id: UUID, payload: DeliveryRequestAccept, actor: User
    ) -> DeliveryRequestRead:
        self.expire_overdue()
        request = self._open_request(request_id, actor)
        order = self._order_of(request)
        route_id = request.route_id if request.route_id is not None else payload.route_id
        if route_id is None:
            raise BusinessRuleError(DeliveryRequestMessages.ROUTE_REQUIRED)
        settings = self._ensure_route_can_serve(request, order, route_id, actor)
        if request.escalated_at is not None and settings is not None:
            self._reschedule(request, order, settings)
        request.status = DeliveryRequestStatus.ACCEPTED
        request.promoter_id = actor.id
        request.route_id = route_id
        request.decided_at = deal_clock_now()
        order.promoter_id = actor.id
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_ACCEPTED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"order_id": str(order.id), "route_id": str(route_id)},
        )
        self._notifications.notify_delivery(
            order.customer_id,
            actor.id,
            NotificationType.DELIVERY_ACCEPTED,
            request.id,
            order.order_number,
        )
        return self._read(request)

    def reject(self, request_id: UUID, actor: User) -> DeliveryRequestRead:
        self.expire_overdue()
        request = self._open_request(request_id, actor)
        if request.promoter_id != actor.id:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        order = self._order_of(request)
        candidates = self._escalate(request, order) if request.escalated_at is None else None
        if candidates is not None:
            self._db.commit()
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.DELIVERY_REJECTED,
                entity_type=ENTITY_TYPE,
                entity_id=request.id,
                metadata={"order_id": str(order.id)},
            )
            self._announce_escalation(request.id, order.order_number, candidates)
            return self._read(request)
        request.status = DeliveryRequestStatus.REJECTED
        request.decided_at = deal_clock_now()
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_REJECTED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"order_id": str(order.id)},
        )
        self._notifications.notify_delivery(
            order.customer_id,
            actor.id,
            NotificationType.DELIVERY_REJECTED,
            request.id,
            order.order_number,
        )
        return self._read(request)

    def re_request(
        self, order_id: UUID, payload: DeliveryReRequest, actor: User
    ) -> DeliveryRequestRead:
        self.expire_overdue()
        order = self._own_order(order_id, actor)
        previous = self._requests.latest_for_order(order.id)
        if previous is None:
            raise NotFoundError(DeliveryRequestMessages.NO_DELIVERY)
        if previous.status not in {DeliveryRequestStatus.REJECTED, DeliveryRequestStatus.EXPIRED}:
            raise BusinessRuleError(DeliveryRequestMessages.NOT_RETRYABLE)
        if order.status not in RESCHEDULABLE_ORDER_STATUSES:
            raise BusinessRuleError(DeliveryRequestMessages.ORDER_CLOSED)
        plan = self._plans.plan(
            previous.option,
            DeliveryTarget.from_order(order),
            payload.route_id,
            self._deal_promoter_id(order),
            deal_clock_now(),
        )
        order.total_amount = order.total_amount - order.delivery_fee + plan.fee
        order.delivery_fee = plan.fee
        for field, value in expected_delivery_fields(plan).items():
            setattr(order, field, value)
        order.promoter_id = plan.promoter_id
        request = self.create(order, plan)
        self._db.commit()
        self.announce(request, plan, order, actor)
        if request is None:
            raise NotFoundError(DeliveryRequestMessages.NO_DELIVERY)
        return self._read(request)

    def stops(
        self, route_id: UUID, delivery_date: date | None, actor: User
    ) -> list[DeliveryStopRead]:
        route = self._routes.get_by_id(route_id)
        if route is None or route.user_id != actor.id:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        day = delivery_date or deal_clock_now().date()
        stops: list[DeliveryStopRead] = []
        for request in self._requests.list_stops(route_id, day):
            order = self._order_of(request)
            stops.append(
                DeliveryStopRead(
                    request_id=request.id,
                    request_status=request.status,
                    order_id=order.id,
                    order_number=order.order_number,
                    order_status=order.status,
                    customer_name=order.customer_name,
                    customer_phone=order.customer_phone,
                    shipping_address=order.shipping_address,
                    destination=_destination(order),
                )
            )
        return stops

    def _open_request(self, request_id: UUID, actor: User) -> DeliveryRequest:
        request = self._requests.get(request_id, for_update=True)
        if request is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        if request.status not in OPEN_STATUSES:
            raise BusinessRuleError(DeliveryRequestMessages.NOT_OPEN)
        if request.promoter_id not in (None, actor.id):
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        if request.passed_over_promoter_id == actor.id:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        return request

    def _escalate(self, request: DeliveryRequest, order: Order) -> tuple[UUID, ...] | None:
        target = DeliveryTarget.from_order(order)
        if target is None:
            return None
        now = deal_clock_now()
        eligible = self._plans.eligible_routes(request.option, target, None, now)
        candidates = tuple(
            dict.fromkeys(
                entry.route.user_id
                for entry in eligible
                if entry.route.user_id != request.promoter_id
            )
        )
        if not candidates:
            return None
        request.passed_over_promoter_id = request.promoter_id
        request.promoter_id = None
        request.route_id = None
        request.escalated_at = now
        request.expires_at = now + self._timeouts.claim_window()
        order.promoter_id = None
        return candidates

    def _announce_escalation(
        self, request_id: UUID, order_number: str, candidates: tuple[UUID, ...]
    ) -> None:
        self._activity_logs.log(
            actor=None,
            action=ActivityAction.DELIVERY_ESCALATED,
            entity_type=ENTITY_TYPE,
            entity_id=request_id,
            metadata={"promoters": len(candidates)},
        )
        for promoter_id in candidates:
            self._notifications.notify_delivery(
                promoter_id, None, NotificationType.DELIVERY_REQUESTED, request_id, order_number
            )

    def _reschedule(
        self, request: DeliveryRequest, order: Order, settings: DeliverySettings
    ) -> None:
        today = deal_clock_now().date()
        if request.option == DeliveryOption.ROUTE:
            request.delivery_date = next_working_day(settings, today)
            order.expected_delivery_from = settings.route_start_time
            order.expected_delivery_to = settings.route_end_time
        else:
            request.delivery_date = today
        order.expected_delivery_date = request.delivery_date

    def _ensure_route_can_serve(
        self, request: DeliveryRequest, order: Order, route_id: UUID, actor: User
    ) -> DeliverySettings | None:
        route = self._routes.get_by_id(route_id)
        if route is None or route.user_id != actor.id or not route.is_active:
            raise BusinessRuleError(DeliveryRequestMessages.ROUTE_CANNOT_SERVE)
        is_instant = request.option == DeliveryOption.INSTANT
        if not is_instant and request.escalated_at is None:
            return None
        settings = self._settings.get_by_user(actor.id)
        fee = (
            None if settings is None else settings.instant_fee if is_instant else settings.route_fee
        )
        if (
            settings is None
            or fee is None
            or (is_instant and not is_within_working_hours(settings, deal_clock_now()))
            or not self._requests.route_covers_order(route_id, order.id)
        ):
            raise BusinessRuleError(DeliveryRequestMessages.ROUTE_CANNOT_SERVE)
        return settings

    def _deal_promoter_id(self, order: Order) -> UUID | None:
        if order.deal_id is None:
            return None
        return self._invitations.accepted_user_id(order.deal_id)

    def _own_order(self, order_id: UUID, actor: User) -> Order:
        order = self._orders.get(order_id)
        if order is None or order.customer_id != actor.id:
            raise NotFoundError(OrderMessages.NOT_FOUND)
        return order

    def _order_of(self, request: DeliveryRequest) -> Order:
        order = self._orders.get(request.order_id)
        if order is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        return order

    def _read(self, request: DeliveryRequest, with_rider: bool = False) -> DeliveryRequestRead:
        order = self._order_of(request)
        route = self._routes.get_by_id(request.route_id) if request.route_id else None
        promoter = (
            self._users.get_by_id_including_deleted(request.promoter_id)
            if request.promoter_id
            else None
        )
        rider = None
        if (
            with_rider
            and request.status == DeliveryRequestStatus.ACCEPTED
            and route is not None
            and route.current_latitude is not None
            and route.current_longitude is not None
            and route.location_updated_at is not None
        ):
            rider = RiderLocationRead(
                location=GeoPoint(
                    latitude=route.current_latitude, longitude=route.current_longitude
                ),
                updated_at=route.location_updated_at,
            )
        return DeliveryRequestRead(
            id=request.id,
            order_id=order.id,
            order_number=order.order_number,
            option=request.option,
            status=request.status,
            delivery_date=request.delivery_date,
            expires_at=request.expires_at,
            decided_at=request.decided_at,
            fee=order.delivery_fee if order.delivery_fee is not None else Decimal(0),
            route_id=request.route_id,
            route_name=route.name if route is not None else None,
            promoter_id=request.promoter_id,
            promoter_name=_person_name(promoter),
            customer_name=order.customer_name,
            shipping_address=order.shipping_address,
            destination=_destination(order),
            open_for_claim=(
                request.status == DeliveryRequestStatus.REQUESTED
                and request.escalated_at is not None
            ),
            rider_location=rider,
        )
