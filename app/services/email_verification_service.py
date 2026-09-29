from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email import send_email_verification_otp
from app.core.exceptions import BusinessRuleError
from app.core.messages import AuthMessages
from app.core.security import generate_otp, hash_password, verify_password
from app.models.user import User
from app.repositories.email_verification_otp_repository import EmailVerificationOtpRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService


class EmailVerificationService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._users = UserRepository(db)
        self._otps = EmailVerificationOtpRepository(db)
        self._activity_logs = ActivityLogService(db)

    def issue_for_registration(self, user: User) -> None:
        self._issue_and_send(user, trigger="registration")

    def resend(self, email: str) -> None:
        user = self._users.get_by_email(email)
        if user is None or user.email_verified_at is not None:
            return
        latest = self._otps.get_latest_for_user(user.id)
        if latest is not None:
            elapsed = datetime.now(UTC) - latest.created_at.replace(tzinfo=UTC)
            if elapsed < timedelta(seconds=self._settings.otp_resend_cooldown_seconds):
                return
        self._issue_and_send(user, trigger="resend")

    def verify(self, email: str, otp: str) -> tuple[User, bool]:
        user = self._users.get_by_email(email)
        if user is None:
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if user.email_verified_at is not None:
            return user, True

        record = self._otps.get_latest_active_for_update(user.id)
        if record is None or record.expires_at < datetime.now(UTC):
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if record.attempts >= self._settings.otp_max_attempts:
            raise BusinessRuleError(AuthMessages.OTP_MAX_ATTEMPTS_EXCEEDED)
        if not verify_password(otp, record.otp_hash):
            self._otps.increment_attempts(record)
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)

        user.email_verified_at = datetime.now(UTC)
        self._otps.delete_all_for_user(user.id)
        self._db.commit()
        self._db.refresh(user)
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.EMAIL_VERIFIED,
            entity_type="user",
            entity_id=user.id,
        )
        return user, False

    def _issue_and_send(self, user: User, trigger: str) -> None:
        self._otps.invalidate_active_for_user(user.id)
        code = generate_otp(self._settings.otp_length)
        expires_at = datetime.now(UTC) + timedelta(minutes=self._settings.otp_expire_minutes)
        self._otps.create(user.id, hash_password(code), expires_at)
        send_email_verification_otp(
            user.email, code, self._settings.otp_expire_minutes, self._settings
        )
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.EMAIL_VERIFICATION_OTP_ISSUED,
            entity_type="user",
            entity_id=user.id,
            metadata={"trigger": trigger},
        )
