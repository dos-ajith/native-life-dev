from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import AuthorizationError, ConflictError
from app.core.jwt import RegistrationTokenType, create_registration_token, parse_registration_token
from app.core.messages import AuthMessages
from app.core.sms import SmsProvider
from app.core.timezone import app_now
from app.models.user import User, UserStatus
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.phone_otp_service import PhoneOtpIssued, PhoneOtpService
from app.services.registration_details import RegistrationDetails
from app.services.session_token_service import IssuedSession, SessionTokenService
from app.services.user_service import UserService, VerifiedAccount

REGISTRATION_SOURCE = "phone"


@dataclass(frozen=True)
class PhoneSignIn:
    user: User | None = None
    session: IssuedSession | None = None
    registration_token: str | None = None


class PhoneAuthService:
    def __init__(self, db: Session, settings: Settings, sms_provider: SmsProvider | None) -> None:
        self._db = db
        self._settings = settings
        self._otp = PhoneOtpService(db, settings, sms_provider)
        self._users = UserRepository(db)
        self._user_service = UserService(db)
        self._sessions = SessionTokenService(db, settings)
        self._activity_logs = ActivityLogService(db)

    def send_otp(self, phone: str, ip_address: str | None) -> PhoneOtpIssued:
        return self._otp.send(phone, ip_address)

    def verify_otp(self, phone: str, otp: str) -> PhoneSignIn:
        self._otp.verify(phone, otp)
        user = self._users.get_by_verified_phone(phone)
        if user is None:
            self._db.commit()
            token = create_registration_token(RegistrationTokenType.PHONE, phone, self._settings)
            return PhoneSignIn(registration_token=token)
        if user.status != UserStatus.ACTIVE:
            self._db.commit()
            raise AuthorizationError(AuthMessages.ACCOUNT_INACTIVE)
        return PhoneSignIn(user=user, session=self._sessions.issue(user))

    def register(self, details: RegistrationDetails) -> tuple[IssuedSession, User]:
        claims = parse_registration_token(
            details.registration_token, RegistrationTokenType.PHONE, self._settings
        )
        phone: str = claims["sub"]
        if self._users.get_by_verified_phone(phone) is not None:
            raise self._phone_taken()
        released = self._users.list_unverified_by_phone(phone)
        for holder in released:
            holder.phone = None
        self._db.flush()
        try:
            user = self._user_service.create_verified_account(
                VerifiedAccount(
                    first_name=details.first_name,
                    last_name=details.last_name,
                    phone=phone,
                    gender=details.gender,
                    date_of_birth=details.date_of_birth,
                ),
                source=REGISTRATION_SOURCE,
                ip_address=details.ip_address,
                user_agent=details.user_agent,
            )
        except IntegrityError as exc:
            self._db.rollback()
            raise self._phone_taken() from exc
        for holder in released:
            self._activity_logs.log(
                actor=user,
                action=ActivityAction.PHONE_CLAIM_RELEASED,
                entity_type="user",
                entity_id=holder.id,
            )
        return self._sessions.issue(user), user

    def send_link_otp(self, user: User, phone: str, ip_address: str | None) -> PhoneOtpIssued:
        self._ensure_can_link(user, phone)
        return self._otp.send(phone, ip_address)

    def link_phone(
        self,
        user: User,
        phone: str,
        otp: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> User:
        self._ensure_can_link(user, phone)
        self._otp.verify(phone, otp)
        released = self._users.list_unverified_by_phone(phone)
        for holder in released:
            if holder.id != user.id:
                holder.phone = None
        self._db.flush()
        user.phone = phone
        user.phone_verified_at = app_now()
        try:
            saved = self._users.save(user)
        except IntegrityError as exc:
            self._db.rollback()
            raise self._phone_taken() from exc
        self._activity_logs.log(
            actor=saved,
            action=ActivityAction.PHONE_VERIFIED,
            entity_type="user",
            entity_id=saved.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        for holder in released:
            if holder.id != saved.id:
                self._activity_logs.log(
                    actor=saved,
                    action=ActivityAction.PHONE_CLAIM_RELEASED,
                    entity_type="user",
                    entity_id=holder.id,
                )
        return saved

    def _ensure_can_link(self, user: User, phone: str) -> None:
        if user.phone_verified_at is not None and user.phone == phone:
            raise ConflictError(
                AuthMessages.PHONE_ALREADY_VERIFIED, errors=[{"code": "phone_already_verified"}]
            )
        if self._users.get_by_verified_phone(phone) is not None:
            raise self._phone_taken()

    @staticmethod
    def _phone_taken() -> ConflictError:
        return ConflictError(
            AuthMessages.PHONE_ALREADY_REGISTERED, errors=[{"code": "phone_already_registered"}]
        )
