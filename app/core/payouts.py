import hashlib
import hmac
import logging
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.core.config import Settings
from app.core.exceptions import BadGatewayError
from app.core.messages import PayoutMessages

logger = logging.getLogger(__name__)

RAZORPAYX_PROVIDER_NAME = "razorpayx"
RAZORPAYX_TIMEOUT_SECONDS = 15.0
CONTACT_TYPE = "vendor"
PAYOUT_PURPOSE = "payout"
BANK_MODE = "IMPS"
UPI_MODE = "UPI"
REFERENCE_MAX_LENGTH = 40
NARRATION_MAX_LENGTH = 30


@dataclass(frozen=True)
class FundAccountRequest:
    reference: str
    holder_name: str
    account_number: str | None
    ifsc: str | None
    upi_id: str | None


@dataclass(frozen=True)
class FundAccount:
    contact_id: str
    fund_account_id: str
    uses_upi: bool


@dataclass(frozen=True)
class PayoutRequest:
    fund_account_id: str
    amount_minor: int
    currency: str
    uses_upi: bool
    reference: str
    narration: str
    idempotency_key: str


@dataclass(frozen=True)
class CreatedPayout:
    payout_id: str
    status: str


class PayoutGateway(Protocol):
    name: str

    def create_fund_account(self, request: FundAccountRequest) -> FundAccount: ...

    def create_payout(self, request: PayoutRequest) -> CreatedPayout: ...

    def webhook_is_authentic(self, body: bytes, signature: str) -> bool: ...


class RazorpayXGateway:
    name: str = RAZORPAYX_PROVIDER_NAME

    def __init__(
        self,
        api_base_url: str,
        key_id: str,
        key_secret: str,
        account_number: str,
        webhook_secret: str | None,
    ) -> None:
        self._api_base_url = api_base_url
        self._key_id = key_id
        self._key_secret = key_secret
        self._account_number = account_number
        self._webhook_secret = webhook_secret

    @classmethod
    def from_settings(cls, settings: Settings) -> "RazorpayXGateway":
        if (
            settings.razorpayx_key_id is None
            or settings.razorpayx_key_secret is None
            or settings.razorpayx_account_number is None
        ):
            raise ValueError("RazorpayX payouts are not configured")
        webhook_secret = (
            settings.razorpayx_webhook_secret.get_secret_value()
            if settings.razorpayx_webhook_secret is not None
            else None
        )
        return cls(
            api_base_url=settings.razorpayx_api_base_url,
            key_id=settings.razorpayx_key_id,
            key_secret=settings.razorpayx_key_secret.get_secret_value(),
            account_number=settings.razorpayx_account_number,
            webhook_secret=webhook_secret,
        )

    def create_fund_account(self, request: FundAccountRequest) -> FundAccount:
        contact = self._request(
            "POST",
            "/contacts",
            {
                "name": request.holder_name,
                "type": CONTACT_TYPE,
                "reference_id": request.reference[:REFERENCE_MAX_LENGTH],
            },
        )
        uses_upi = request.account_number is None
        details: dict[str, Any] = (
            {"account_type": "vpa", "vpa": {"address": request.upi_id}}
            if uses_upi
            else {
                "account_type": "bank_account",
                "bank_account": {
                    "name": request.holder_name,
                    "ifsc": request.ifsc,
                    "account_number": request.account_number,
                },
            }
        )
        fund_account = self._request(
            "POST", "/fund_accounts", {"contact_id": contact["id"], **details}
        )
        return FundAccount(str(contact["id"]), str(fund_account["id"]), uses_upi)

    def create_payout(self, request: PayoutRequest) -> CreatedPayout:
        body = self._request(
            "POST",
            "/payouts",
            {
                "account_number": self._account_number,
                "fund_account_id": request.fund_account_id,
                "amount": request.amount_minor,
                "currency": request.currency,
                "mode": UPI_MODE if request.uses_upi else BANK_MODE,
                "purpose": PAYOUT_PURPOSE,
                "queue_if_low_balance": True,
                "reference_id": request.reference[:REFERENCE_MAX_LENGTH],
                "narration": request.narration[:NARRATION_MAX_LENGTH],
            },
            {"X-Payout-Idempotency": request.idempotency_key},
        )
        return CreatedPayout(str(body["id"]), str(body.get("status", "")))

    def webhook_is_authentic(self, body: bytes, signature: str) -> bool:
        if self._webhook_secret is None:
            return False
        expected = hmac.new(self._webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    def _request(
        self,
        method: str,
        path: str,
        json: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            with httpx.Client(
                base_url=self._api_base_url,
                auth=(self._key_id, self._key_secret),
                timeout=RAZORPAYX_TIMEOUT_SECONDS,
            ) as client:
                response = client.request(method, path, json=json, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("RazorpayX unreachable on %s %s: %s", method, path, type(exc).__name__)
            raise BadGatewayError(PayoutMessages.RAZORPAYX_FAILED) from exc
        if response.is_error:
            logger.warning(
                "RazorpayX rejected %s %s: status=%s body=%s",
                method,
                path,
                response.status_code,
                response.text[:500],
            )
            raise BadGatewayError(PayoutMessages.RAZORPAYX_FAILED)
        return response.json()


def get_payout_gateway(settings: Settings) -> PayoutGateway | None:
    if settings.payout_provider == "razorpayx":
        return RazorpayXGateway.from_settings(settings)
    return None
