import hashlib
import hmac
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import BadGatewayError
from app.core.messages import PaymentMessages

logger = logging.getLogger(__name__)

RAZORPAY_PROVIDER_NAME = "razorpay"
RAZORPAY_CALLBACK_METHOD = "get"
RAZORPAY_REFERENCE_MAX_LENGTH = 40


@dataclass(frozen=True)
class PaymentLinkRequest:
    reference: str
    amount_minor: int
    currency: str
    description: str
    customer_name: str
    customer_phone: str
    expires_at: datetime
    notes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CreatedPaymentLink:
    link_id: str
    url: str


@dataclass(frozen=True)
class PaymentLinkState:
    link_id: str
    status: str
    payment_id: str | None


@dataclass(frozen=True)
class PaymentCallback:
    link_id: str
    reference: str
    status: str
    payment_id: str
    signature: str


class PaymentGateway(Protocol):
    name: str

    def create_link(self, request: PaymentLinkRequest) -> CreatedPaymentLink: ...

    def fetch_link(self, link_id: str) -> PaymentLinkState: ...

    def callback_is_authentic(self, callback: PaymentCallback) -> bool: ...

    def webhook_is_authentic(self, body: bytes, signature: str) -> bool: ...


def _customer(request: PaymentLinkRequest) -> dict[str, str]:
    customer = {"name": request.customer_name}
    if request.customer_phone:
        customer["contact"] = request.customer_phone
    return customer


def _hmac_matches(secret: str, message: bytes, signature: str) -> bool:
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


class RazorpayGateway:
    name: str = RAZORPAY_PROVIDER_NAME

    def __init__(
        self,
        api_base_url: str,
        key_id: str,
        key_secret: str,
        webhook_secret: str | None,
        callback_url: str,
        timeout_seconds: float,
    ) -> None:
        self._api_base_url = api_base_url
        self._key_id = key_id
        self._timeout_seconds = timeout_seconds
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._callback_url = callback_url

    @classmethod
    def from_settings(cls, settings: Settings) -> "RazorpayGateway":
        if (
            settings.razorpay_key_id is None
            or settings.razorpay_key_secret is None
            or settings.payment_callback_url is None
        ):
            raise ValueError("Razorpay payment gateway is not configured")
        webhook_secret = (
            settings.razorpay_webhook_secret.get_secret_value()
            if settings.razorpay_webhook_secret is not None
            else None
        )
        return cls(
            api_base_url=settings.razorpay_api_base_url,
            key_id=settings.razorpay_key_id,
            key_secret=settings.razorpay_key_secret.get_secret_value(),
            webhook_secret=webhook_secret,
            callback_url=settings.payment_callback_url,
            timeout_seconds=settings.razorpay_request_timeout_seconds,
        )

    def create_link(self, request: PaymentLinkRequest) -> CreatedPaymentLink:
        body = self._request(
            "POST",
            "/payment_links",
            json={
                "amount": request.amount_minor,
                "currency": request.currency,
                "accept_partial": False,
                "reference_id": request.reference[:RAZORPAY_REFERENCE_MAX_LENGTH],
                "description": request.description,
                "customer": _customer(request),
                "notify": {"sms": False, "email": False},
                "reminder_enable": False,
                "expire_by": int(request.expires_at.timestamp()),
                "callback_url": self._callback_url,
                "callback_method": RAZORPAY_CALLBACK_METHOD,
                "notes": request.notes,
            },
        )
        return CreatedPaymentLink(link_id=str(body["id"]), url=str(body["short_url"]))

    def fetch_link(self, link_id: str) -> PaymentLinkState:
        body = self._request("GET", f"/payment_links/{link_id}")
        payments = body.get("payments") or []
        payment_id = next(
            (str(item["payment_id"]) for item in payments if item.get("status") == "captured"),
            None,
        )
        return PaymentLinkState(
            link_id=str(body["id"]), status=str(body["status"]), payment_id=payment_id
        )

    def callback_is_authentic(self, callback: PaymentCallback) -> bool:
        message = (
            f"{callback.link_id}|{callback.reference}|{callback.status}|{callback.payment_id}"
        ).encode()
        return _hmac_matches(self._key_secret, message, callback.signature)

    def webhook_is_authentic(self, body: bytes, signature: str) -> bool:
        if self._webhook_secret is None:
            return False
        return _hmac_matches(self._webhook_secret, body, signature)

    def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        try:
            with httpx.Client(
                base_url=self._api_base_url,
                auth=(self._key_id, self._key_secret),
                timeout=self._timeout_seconds,
            ) as client:
                response = client.request(method, path, json=json)
        except httpx.HTTPError as exc:
            logger.warning("Razorpay unreachable on %s %s: %s", method, path, type(exc).__name__)
            raise BadGatewayError(PaymentMessages.GATEWAY_FAILED) from exc
        if response.is_error:
            logger.warning(
                "Razorpay rejected %s %s: status=%s body=%s",
                method,
                path,
                response.status_code,
                response.text[:500],
            )
            raise BadGatewayError(PaymentMessages.GATEWAY_FAILED)
        return response.json()


def get_payment_gateway(settings: Settings) -> PaymentGateway | None:
    if settings.payment_provider == "razorpay":
        return RazorpayGateway.from_settings(settings)
    return None
