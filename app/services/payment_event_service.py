import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.exceptions import AuthenticationError, NotFoundError, ServiceUnavailableError
from app.core.messages import PaymentMessages
from app.core.payments import PaymentCallback, PaymentGateway
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.schemas.payment import PaymentStatusRead
from app.services.booking_payment_service import BookingPaymentService
from app.services.dues_service import DuesService
from app.services.order_payment_service import OrderPaymentService

WEBHOOK_LINK_EVENTS = frozenset(
    {"payment_link.paid", "payment_link.expired", "payment_link.cancelled"}
)


class PaymentEventService:
    def __init__(
        self,
        db: Session,
        gateway: PaymentGateway | None,
        registry: PluginRegistry | None = None,
    ) -> None:
        self._gateway = gateway
        self._bookings = BookingPaymentService(db, gateway)
        self._orders = OrderPaymentService(db, gateway, registry)
        self._dues = DuesService(db, gateway)

    def record_callback(self, callback: PaymentCallback) -> PaymentStatusRead:
        if not self._require_gateway().callback_is_authentic(callback):
            raise AuthenticationError(PaymentMessages.SIGNATURE_INVALID)
        settled = self._settle(callback.link_id, callback.status, callback.payment_id, None)
        if settled is None:
            raise NotFoundError(PaymentMessages.NO_PAYMENT)
        return settled

    def record_webhook(self, body: bytes, signature: str) -> None:
        if not self._require_gateway().webhook_is_authentic(body, signature):
            raise AuthenticationError(PaymentMessages.SIGNATURE_INVALID)
        event: dict[str, Any] = json.loads(body)
        if event.get("event") not in WEBHOOK_LINK_EVENTS:
            return
        payload = event.get("payload", {})
        link = payload.get("payment_link", {}).get("entity", {})
        payment_id = payload.get("payment", {}).get("entity", {}).get("id")
        self._settle(str(link.get("id", "")), str(link.get("status", "")), payment_id, None)

    def _settle(
        self,
        link_id: str,
        gateway_status: str,
        provider_payment_id: str | None,
        actor: User | None,
    ) -> PaymentStatusRead | None:
        booking = self._bookings.settle_link(link_id, gateway_status, provider_payment_id, actor)
        if booking is not None:
            return booking
        order = self._orders.settle_link(link_id, gateway_status, provider_payment_id, actor)
        if order is not None:
            return order
        return self._dues.settle_link(link_id, gateway_status, provider_payment_id, actor)

    def _require_gateway(self) -> PaymentGateway:
        if self._gateway is None:
            raise ServiceUnavailableError(PaymentMessages.GATEWAY_DISABLED)
        return self._gateway
