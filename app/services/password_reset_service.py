from datetime import timedelta

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email_templates import render_password_reset_otp_email
from app.core.exceptions import BusinessRuleError
from app.core.messages import AuthMessages
from app.core.security import generate_otp, hash_password, verify_password
from app.core.timezone import app_now
from app.models.email import EmailType
from app.models.user import User, UserStatus, UserType
from app.repositories.password_reset_otp_repository import PasswordResetOtpRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.email_service import EmailService
from app.services.session_token_service import SessionTokenService


class PasswordResetService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._users = UserRepository(db)
        self._otps = PasswordResetOtpRepository(db)
        self._sessions = SessionTokenService(db, settings)
        self._activity_logs = ActivityLogService(db)
        self._emails = EmailService(db, settings)

    def request(self, email: str, background_tasks: BackgroundTasks) -> None:
        user = self._users.get_by_email(email)
        if user is None or user.email is None or not self._is_eligible(user):
            return
        cooldown = timedelta(seconds=self._settings.otp_resend_cooldown_seconds)
        if self._otps.remaining_cooldown_seconds(user.id, cooldown) > 0:
            return
        self._issue_and_send(user, user.email, background_tasks)

    def reset(self, email: str, otp: str, new_password: str) -> None:
        user = self._users.get_by_email(email)
        if user is None or not self._is_eligible(user):
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        self._verify_otp(user, otp)
        user.password_hash = hash_password(new_password)
        self._otps.delete_all_for_user(user.id)
        self._sessions.revoke_all_for_user(user.id)
        self._db.commit()
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.PASSWORD_RESET_COMPLETED,
            entity_type="user",
            entity_id=user.id,
        )

    @staticmethod
    def _is_eligible(user: User) -> bool:
        if user.status != UserStatus.ACTIVE:
            return False
        return user.email_verified_at is not None or user.user_type == UserType.PRIVATE

    def _verify_otp(self, user: User, otp: str) -> None:
        record = self._otps.get_latest_active_for_update(user.id)
        if record is None or record.expires_at < app_now():
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if record.attempts >= self._settings.otp_max_attempts:
            raise BusinessRuleError(AuthMessages.OTP_MAX_ATTEMPTS_EXCEEDED)
        if not verify_password(otp, record.otp_hash):
            self._otps.increment_attempts(record)
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)

    def _issue_and_send(self, user: User, to_email: str, background_tasks: BackgroundTasks) -> None:
        self._otps.invalidate_active_for_user(user.id)
        code = generate_otp(self._settings.otp_length)
        expires_at = app_now() + timedelta(minutes=self._settings.otp_expire_minutes)
        self._otps.create(user.id, hash_password(code), expires_at)
        content = render_password_reset_otp_email(
            app_name=self._settings.app_name,
            otp=code,
            expire_minutes=self._settings.otp_expire_minutes,
            support_url=self._settings.support_url,
            privacy_policy_url=self._settings.privacy_policy_url,
            terms_of_service_url=self._settings.terms_of_service_url,
        )
        self._emails.send(
            background_tasks,
            email_type=EmailType.PASSWORD_RESET,
            to_email=to_email,
            subject=content.subject,
            text_body=content.text_body,
            html_body=content.html_body,
            user_id=user.id,
        )
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.PASSWORD_RESET_OTP_ISSUED,
            entity_type="user",
            entity_id=user.id,
        )
