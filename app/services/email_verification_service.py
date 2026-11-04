from datetime import timedelta

from fastapi import BackgroundTasks
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email_templates import render_verification_otp_email
from app.core.exceptions import BusinessRuleError, ConflictError, TooManyRequestsError
from app.core.messages import AuthMessages, UserMessages
from app.core.security import generate_otp, hash_password, verify_password
from app.core.timezone import app_now
from app.models.email import EmailType
from app.models.user import User
from app.repositories.email_verification_otp_repository import EmailVerificationOtpRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.email_domain_policy import ensure_email_domain_allowed
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
        self._enforce_cooldown(user)
        self._issue_and_send(user, trigger="resend", background_tasks=background_tasks)

    def verify(self, email: str, otp: str) -> tuple[User, bool]:
        user = self._users.get_by_email(email)
        if user is None:
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if user.email_verified_at is not None:
            return user, True
        self._consume_otp(user, otp)
        return user, False

    def send_link_otp(self, user: User, email: str, background_tasks: BackgroundTasks) -> None:
        ensure_email_domain_allowed(email, self._settings)
        self._ensure_can_link(user, email)
        if user.email != email:
            user.email = email
            try:
                self._users.save(user)
            except IntegrityError as exc:
                self._db.rollback()
                raise ConflictError(UserMessages.EMAIL_TAKEN) from exc
        self._enforce_cooldown(user)
        self._issue_and_send(user, trigger="link", background_tasks=background_tasks)

    def link_email(self, user: User, email: str, otp: str) -> User:
        if user.email_verified_at is not None:
            raise self._already_verified()
        if user.email != email:
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        self._consume_otp(user, otp)
        return user

    def _ensure_can_link(self, user: User, email: str) -> None:
        if user.email_verified_at is not None:
            raise self._already_verified()
        holder = self._users.get_by_email_ignoring_case(email)
        if holder is not None and holder.id != user.id:
            raise ConflictError(UserMessages.EMAIL_TAKEN, errors=[{"code": "email_taken"}])

    @staticmethod
    def _already_verified() -> ConflictError:
        return ConflictError(
            AuthMessages.EMAIL_ALREADY_VERIFIED, errors=[{"code": "email_already_verified"}]
        )

    def _enforce_cooldown(self, user: User) -> None:
        cooldown = timedelta(seconds=self._settings.otp_resend_cooldown_seconds)
        remaining = self._otps.remaining_cooldown_seconds(user.id, cooldown)
        if remaining > 0:
            raise TooManyRequestsError(
                AuthMessages.OTP_RESEND_COOLDOWN.format(seconds=remaining),
                errors=[{"retry_after_seconds": remaining}],
            )

    def _consume_otp(self, user: User, otp: str) -> None:
        record = self._otps.get_latest_active_for_update(user.id)
        if record is None or record.expires_at < app_now():
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)
        if record.attempts >= self._settings.otp_max_attempts:
            raise BusinessRuleError(AuthMessages.OTP_MAX_ATTEMPTS_EXCEEDED)
        if not verify_password(otp, record.otp_hash):
            self._otps.increment_attempts(record)
            raise BusinessRuleError(AuthMessages.INVALID_OR_EXPIRED_OTP)

        user.email_verified_at = app_now()
        self._otps.delete_all_for_user(user.id)
        self._db.commit()
        self._db.refresh(user)
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.EMAIL_VERIFIED,
            entity_type="user",
            entity_id=user.id,
        )

    def _issue_and_send(self, user: User, trigger: str, background_tasks: BackgroundTasks) -> None:
        if user.email is None:
            return
        self._otps.invalidate_active_for_user(user.id)
        code = generate_otp(self._settings.otp_length)
        expires_at = app_now() + timedelta(minutes=self._settings.otp_expire_minutes)
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
