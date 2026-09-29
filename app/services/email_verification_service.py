from datetime import UTC, timedelta

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email_templates import render_verification_otp_email
from app.core.exceptions import BusinessRuleError
from app.core.messages import AuthMessages
from app.core.security import generate_otp, hash_password, verify_password
from app.core.timezone import app_now_utc
from app.models.email import EmailType
from app.models.user import User
from app.repositories.email_verification_otp_repository import EmailVerificationOtpRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.email_service import EmailService


class EmailVerificationService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._users = UserRepository(db)
        self._otps = EmailVerificationOtpRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._emails = EmailService(db, settings)

    def issue_for_registration(self, user: User, background_tasks: BackgroundTasks) -> None:
        self._issue_and_send(user, trigger="registration", background_tasks=background_tasks)

    def resend(self, email: str, background_tasks: BackgroundTasks) -> None:
        user = self._users.get_by_email(email)
        if user is None or user.email_verified_at is not None:
            return
        latest = self._otps.get_latest_for_user(user.id)
        if latest is not None:
            elapsed = app_now_utc(self._settings) - latest.created_at.replace(tzinfo=UTC)
            if elapsed < timedelta(seconds=self._settings.otp_resend_cooldown_seconds):
                return
        self._issue_and_send(user, trigger="resend", background_tasks=background_tasks)

    def verify(self, email: str, otp: str) -> tuple[User, bool]:
        user = self._users.get_by_email(email)
        if user is None:
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if user.email_verified_at is not None:
            return user, True

        record = self._otps.get_latest_active_for_update(user.id)
        if record is None or record.expires_at < app_now_utc(self._settings):
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if record.attempts >= self._settings.otp_max_attempts:
            raise BusinessRuleError(AuthMessages.OTP_MAX_ATTEMPTS_EXCEEDED)
        if not verify_password(otp, record.otp_hash):
            self._otps.increment_attempts(record)
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)

        user.email_verified_at = app_now_utc(self._settings)
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

    def _issue_and_send(
        self, user: User, trigger: str, background_tasks: BackgroundTasks
    ) -> None:
        self._otps.invalidate_active_for_user(user.id)
        code = generate_otp(self._settings.otp_length)
        expires_at = app_now_utc(self._settings) + timedelta(
            minutes=self._settings.otp_expire_minutes
        )
        self._otps.create(user.id, hash_password(code), expires_at)
        content = render_verification_otp_email(
            app_name=self._settings.app_name,
            otp=code,
            expire_minutes=self._settings.otp_expire_minutes,
            support_url=self._settings.support_url,
            privacy_policy_url=self._settings.privacy_policy_url,
            terms_of_service_url=self._settings.terms_of_service_url,
        )
        self._emails.send(
            background_tasks,
            email_type=EmailType.EMAIL_VERIFICATION,
            to_email=user.email,
            subject=content.subject,
            text_body=content.text_body,
            html_body=content.html_body,
            user_id=user.id,
        )
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.EMAIL_VERIFICATION_OTP_ISSUED,
            entity_type="user",
            entity_id=user.id,
            metadata={"trigger": trigger},
        )
