import hashlib
import hmac
from datetime import datetime, timedelta
from uuid import UUID

from app.core.config import get_settings
from app.models.delivery_request import DeliveryRequest

HANDOVER_OTP_LENGTH = 6
HANDOVER_OTP_VALID_HOURS = 24
HANDOVER_OTP_MAX_ATTEMPTS = 5
HANDOVER_OTP_RESEND_SECONDS = 30
HANDOVER_OTP_PURPOSE = "delivery-handover"


def handover_otp(request_id: UUID, version: int) -> str:
    key = get_settings().jwt_secret_key.encode()
    message = f"{HANDOVER_OTP_PURPOSE}:{request_id}:{version}".encode()
    digest = hmac.new(key, message, hashlib.sha256).digest()
    number = int.from_bytes(digest[:8], "big") % 10**HANDOVER_OTP_LENGTH
    return f"{number:0{HANDOVER_OTP_LENGTH}d}"


def otp_matches(request: DeliveryRequest, supplied: str) -> bool:
    expected = handover_otp(request.id, request.handover_otp_version)
    return hmac.compare_digest(expected.encode(), supplied.encode())


def otp_expires_at(request: DeliveryRequest) -> datetime | None:
    if request.started_at is None:
        return None
    return request.started_at + timedelta(hours=HANDOVER_OTP_VALID_HOURS)


def otp_is_active(request: DeliveryRequest, now: datetime) -> bool:
    expires_at = otp_expires_at(request)
    return (
        expires_at is not None
        and now <= expires_at
        and request.handover_otp_attempts < HANDOVER_OTP_MAX_ATTEMPTS
    )
