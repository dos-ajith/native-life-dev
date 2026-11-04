from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, ServiceUnavailableError, TooManyRequestsError
from app.core.messages import AuthMessages
from app.core.security import generate_otp, hash_password, verify_password
from app.core.sms import OutgoingSms, SmsProvider
from app.core.sms_templates import render_phone_otp_sms
from app.core.timezone import app_now
from app.models.phone_otp_challenge import PhoneOtpChallenge
from app.repositories.phone_otp_challenge_repository import PhoneOtpChallengeRepository
from app.services.activity_log_service import ActivityLogService

SECONDS_PER_MINUTE = 60
RATE_LIMIT_WINDOW = timedelta(hours=1)


@dataclass(frozen=True)
class PhoneOtpIssued:
    expires_in_seconds: int
    resend_available_in_seconds: int


class PhoneOtpService:
    def __init__(self, db: Session, settings: Settings, sms_provider: SmsProvider | None) -> None:
        self._db = db
        self._settings = settings
        self._sms = sms_provider
        self._challenges = PhoneOtpChallengeRepository(db)
        self._activity_logs = ActivityLogService(db)

    def send(self, phone: str, ip_address: str | None) -> PhoneOtpIssued:
        if self._sms is None:
            raise ServiceUnavailableError(
                AuthMessages.SMS_UNAVAILABLE, errors=[{"code": "sms_unavailable"}]
            )
        self._challenges.lock_phone(phone)
        self._enforce_limits(phone, ip_address)
        self._challenges.invalidate_active(phone)
        code = generate_otp(self._settings.otp_length)
        challenge = PhoneOtpChallenge(
            phone=phone,
            otp_hash=hash_password(code),
            ip_address=ip_address,
            expires_at=app_now() + timedelta(minutes=self._settings.otp_expire_minutes),
        )
        self._challenges.add(challenge)
        self._db.commit()
        body = render_phone_otp_sms(
            self._settings.app_name, code, self._settings.otp_expire_minutes
        )
        result = self._sms.send(OutgoingSms(to_phone=phone, body=body))
        if not result.success:
            challenge.consumed_at = app_now()
            self._db.commit()
            raise ServiceUnavailableError(
                AuthMessages.SMS_SEND_FAILED, errors=[{"code": "sms_send_failed"}]
            )
        self._activity_logs.log(
            actor=None,
            action=ActivityAction.PHONE_OTP_ISSUED,
            entity_type="phone_otp_challenge",
            entity_id=challenge.id,
            metadata={"sms_provider": self._sms.name},
            ip_address=ip_address,
        )
        return PhoneOtpIssued(
            expires_in_seconds=self._settings.otp_expire_minutes * SECONDS_PER_MINUTE,
            resend_available_in_seconds=self._settings.otp_resend_cooldown_seconds,
        )

    def verify(self, phone: str, otp: str) -> PhoneOtpChallenge:
        challenge = self._challenges.get_latest_active_for_update(phone)
        if challenge is None or challenge.expires_at <= app_now():
            raise BusinessRuleError(
                AuthMessages.INVALID_OR_EXPIRED_OTP, errors=[{"code": "otp_invalid"}]
            )
        if challenge.attempts >= self._settings.otp_max_attempts:
            raise BusinessRuleError(
                AuthMessages.OTP_MAX_ATTEMPTS_EXCEEDED, errors=[{"code": "otp_attempts_exceeded"}]
            )
        if not verify_password(otp, challenge.otp_hash):
            challenge.attempts += 1
            self._db.commit()
            raise BusinessRuleError(
                AuthMessages.INVALID_OR_EXPIRED_OTP, errors=[{"code": "otp_invalid"}]
            )
        challenge.consumed_at = app_now()
        return challenge

    def _enforce_limits(self, phone: str, ip_address: str | None) -> None:
        cooldown = timedelta(seconds=self._settings.otp_resend_cooldown_seconds)
        remaining = self._challenges.remaining_cooldown_seconds(phone, cooldown)
        if remaining > 0:
            raise TooManyRequestsError(
                AuthMessages.OTP_RESEND_COOLDOWN.format(seconds=remaining),
                errors=[{"code": "otp_resend_cooldown", "retry_after_seconds": remaining}],
            )
        phone_limit = self._settings.phone_otp_max_sends_per_phone_per_hour
        ip_limit = self._settings.phone_otp_max_sends_per_ip_per_hour
        phone_exhausted = (
            self._challenges.count_for_phone_since(phone, RATE_LIMIT_WINDOW) >= phone_limit
        )
        ip_exhausted = ip_address is not None and (
            self._challenges.count_for_ip_since(ip_address, RATE_LIMIT_WINDOW) >= ip_limit
        )
        if phone_exhausted or ip_exhausted:
            raise TooManyRequestsError(
                AuthMessages.PHONE_OTP_RATE_LIMITED, errors=[{"code": "otp_rate_limited"}]
            )
