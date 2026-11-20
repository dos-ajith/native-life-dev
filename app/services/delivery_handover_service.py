from datetime import datetime, timedelta
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import DeliveryRequestMessages
from app.core.storage import delete_private_document, save_delivery_proof
from app.models.delivery_request import DeliveryRequest, DeliveryRequestStatus
from app.models.notification import NotificationType
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.repositories.delivery_request_repository import DeliveryRequestRepository
from app.repositories.order_repository import OrderRepository
from app.services.activity_log_service import ActivityLogService
from app.services.deal_expiry_service import deal_clock_now
from app.services.handover_otp import (
    HANDOVER_OTP_MAX_ATTEMPTS,
    HANDOVER_OTP_RESEND_SECONDS,
    handover_otp,
    otp_expires_at,
    otp_is_active,
    otp_matches,
)
from app.services.notification_service import NotificationService
from app.services.order_fulfilment import OrderFulfilment
from app.services.order_payment_service import ensure_paid_if_online

ENTITY_TYPE = "delivery_request"
STARTABLE_ORDER_STATUSES = frozenset({OrderStatus.CONFIRMED, OrderStatus.SHIPPED})


class DeliveryHandoverService:
    def __init__(self, db: Session, private_upload_dir: str) -> None:
        self._db = db
        self._private_upload_dir = private_upload_dir
        self._requests = DeliveryRequestRepository(db)
        self._orders = OrderRepository(db)
        self._fulfilment = OrderFulfilment(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def start(self, request_id: UUID, actor: User) -> None:
        request = self._assigned_request(request_id, actor)
        self._ensure_deliverable(request)
        order = self._order_of(request)
        now = deal_clock_now()
        if request.delivery_date > now.date():
            raise BusinessRuleError(DeliveryRequestMessages.TOO_EARLY)
        if order.status not in STARTABLE_ORDER_STATUSES:
            raise BusinessRuleError(DeliveryRequestMessages.ORDER_NOT_CONFIRMED)
        ensure_paid_if_online(order)
        if otp_is_active(request, now):
            self._resend(request, order, actor, now)
            return
        request.started_at = now
        request.handover_otp_version += 1
        request.handover_otp_attempts = 0
        if order.status == OrderStatus.CONFIRMED:
            self._fulfilment.change_status(order, OrderStatus.SHIPPED, actor)
        else:
            self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_STARTED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"order_id": str(order.id)},
        )
        self._send_otp(request, order, actor)

    def _resend(self, request: DeliveryRequest, order: Order, actor: User, now: datetime) -> None:
        since = now - timedelta(seconds=HANDOVER_OTP_RESEND_SECONDS)
        if self._notifications.delivery_notified_since(
            order.customer_id, NotificationType.DELIVERY_STARTED, request.id, since
        ):
            raise BusinessRuleError(DeliveryRequestMessages.OTP_RESEND_TOO_SOON)
        self._send_otp(request, order, actor)

    def _send_otp(self, request: DeliveryRequest, order: Order, actor: User) -> None:
        self._notifications.notify_delivery(
            order.customer_id,
            actor.id,
            NotificationType.DELIVERY_STARTED,
            request.id,
            order.order_number,
            handover_otp=handover_otp(request.id, request.handover_otp_version),
        )

    def complete(self, request_id: UUID, otp: str, proof: UploadFile, actor: User) -> None:
        request = self._assigned_request(request_id, actor)
        self._ensure_deliverable(request)
        expires_at = otp_expires_at(request)
        if expires_at is None:
            raise BusinessRuleError(DeliveryRequestMessages.NOT_STARTED)
        if request.handover_otp_attempts >= HANDOVER_OTP_MAX_ATTEMPTS:
            raise BusinessRuleError(DeliveryRequestMessages.OTP_LOCKED)
        now = deal_clock_now()
        if now > expires_at:
            raise BusinessRuleError(DeliveryRequestMessages.OTP_EXPIRED)
        if not otp_matches(request, otp):
            request.handover_otp_attempts += 1
            self._db.commit()
            raise BusinessRuleError(DeliveryRequestMessages.OTP_INVALID)
        order = self._order_of(request)
        proof_path = save_delivery_proof(proof, self._private_upload_dir)
        try:
            request.status = DeliveryRequestStatus.DELIVERED
            request.delivered_at = now
            request.delivered_by_id = actor.id
            request.proof_image_path = proof_path
            self._fulfilment.change_status(order, OrderStatus.DELIVERED, actor, via_delivery=True)
        except Exception:
            self._db.rollback()
            delete_private_document(proof_path)
            raise
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_COMPLETED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"order_id": str(order.id)},
        )
        self._notifications.notify_delivery(
            order.customer_id,
            actor.id,
            NotificationType.DELIVERY_DELIVERED,
            request.id,
            order.order_number,
        )

    def _assigned_request(self, request_id: UUID, actor: User) -> DeliveryRequest:
        if self._requests.get_for_courier(request_id, actor.id) is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        locked = self._requests.get(request_id, for_update=True)
        if locked is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        return locked

    def _ensure_deliverable(self, request: DeliveryRequest) -> None:
        if request.status == DeliveryRequestStatus.DELIVERED:
            raise BusinessRuleError(DeliveryRequestMessages.ALREADY_DELIVERED)
        if request.status != DeliveryRequestStatus.ACCEPTED:
            raise BusinessRuleError(DeliveryRequestMessages.NOT_DELIVERABLE)

    def _order_of(self, request: DeliveryRequest) -> Order:
        order = self._orders.get(request.order_id)
        if order is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        return order
