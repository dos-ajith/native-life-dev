from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    ServiceUnavailableError,
)
from app.core.google_auth import GoogleIdentity, GoogleTokenVerifier
from app.core.jwt import RegistrationTokenType, create_registration_token, parse_registration_token
from app.core.messages import AuthMessages
from app.models.auth_identity import AuthIdentity, AuthProvider
from app.models.user import User, UserStatus
from app.repositories.auth_identity_repository import AuthIdentityRepository
from app.repositories.user_repository import UserRepository
from app.services.activity_log_service import ActivityLogService
from app.services.registration_details import RegistrationDetails
from app.services.session_token_service import IssuedSession, SessionTokenService
from app.services.user_service import UserService, VerifiedAccount

REGISTRATION_SOURCE = "google"
EMAIL_CLAIM = "email"


@dataclass(frozen=True)
class GoogleSignIn:
    user: User | None = None
    session: IssuedSession | None = None
    registration_token: str | None = None
    identity: GoogleIdentity | None = None


class GoogleAuthService:
    def __init__(
        self, db: Session, settings: Settings, verifier: GoogleTokenVerifier | None
    ) -> None:
        self._db = db
        self._settings = settings
        self._verifier = verifier
        self._identities = AuthIdentityRepository(db)
        self._users = UserRepository(db)
        self._user_service = UserService(db)
        self._sessions = SessionTokenService(db, settings)
        self._activity_logs = ActivityLogService(db)

    def sign_in(self, id_token: str) -> GoogleSignIn:
        google = self._verify(id_token)
        linked = self._identities.get(AuthProvider.GOOGLE, google.subject)
        if linked is not None:
            user = self._users.get_by_id(linked.user_id)
            if user is None or user.status != UserStatus.ACTIVE:
                raise AuthorizationError(AuthMessages.ACCOUNT_INACTIVE)
            return GoogleSignIn(user=user, session=self._sessions.issue(user))
        email = self._require_unclaimed_email(google)
        token = create_registration_token(
            RegistrationTokenType.GOOGLE,
            google.subject,
            self._settings,
            extra_claims={EMAIL_CLAIM: email},
        )
        return GoogleSignIn(registration_token=token, identity=google)

    def register(self, details: RegistrationDetails) -> tuple[IssuedSession, User]:
        claims = parse_registration_token(
            details.registration_token, RegistrationTokenType.GOOGLE, self._settings
        )
        subject: str = claims["sub"]
        email: str = claims[EMAIL_CLAIM]
        if self._identities.get(AuthProvider.GOOGLE, subject) is not None:
            raise self._identity_in_use()
        if self._users.get_by_email_ignoring_case(email) is not None:
            raise self._account_exists()
        identity = AuthIdentity(provider=AuthProvider.GOOGLE, subject=subject, email=email)
        try:
            user = self._user_service.create_verified_account(
                VerifiedAccount(
                    first_name=details.first_name,
                    last_name=details.last_name,
                    email=email,
                    identities=[identity],
                    gender=details.gender,
                    date_of_birth=details.date_of_birth,
                ),
                source=REGISTRATION_SOURCE,
                ip_address=details.ip_address,
                user_agent=details.user_agent,
            )
        except IntegrityError as exc:
            self._db.rollback()
            raise self._account_exists() from exc
        self._log_linked(user, identity, details.ip_address, details.user_agent)
        return self._sessions.issue(user), user

    def link(
        self,
        user: User,
        id_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuthIdentity:
        google = self._verify(id_token)
        linked = self._identities.get(AuthProvider.GOOGLE, google.subject)
        if linked is not None:
            if linked.user_id == user.id:
                return linked
            raise self._identity_in_use()
        if self._identities.get_for_user(user.id, AuthProvider.GOOGLE) is not None:
            raise ConflictError(
                AuthMessages.GOOGLE_ALREADY_LINKED, errors=[{"code": "google_already_linked"}]
            )
        try:
            identity = self._identities.add(
                AuthIdentity(
                    user_id=user.id,
                    provider=AuthProvider.GOOGLE,
                    subject=google.subject,
                    email=google.email,
                )
            )
        except IntegrityError as exc:
            self._db.rollback()
            raise self._identity_in_use() from exc
        self._log_linked(user, identity, ip_address, user_agent)
        return identity

    def _verify(self, id_token: str) -> GoogleIdentity:
        if self._verifier is None:
            raise ServiceUnavailableError(
                AuthMessages.GOOGLE_UNAVAILABLE, errors=[{"code": "google_unavailable"}]
            )
        google = self._verifier.verify(id_token)
        if not google.email_verified or not google.email:
            raise BusinessRuleError(
                AuthMessages.GOOGLE_EMAIL_NOT_VERIFIED,
                errors=[{"code": "google_email_not_verified"}],
            )
        return google

    def _require_unclaimed_email(self, google: GoogleIdentity) -> str:
        assert google.email is not None
        if self._users.get_by_email_ignoring_case(google.email) is not None:
            raise self._account_exists()
        return google.email

    def _log_linked(
        self,
        user: User,
        identity: AuthIdentity,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.AUTH_IDENTITY_LINKED,
            entity_type="auth_identity",
            entity_id=identity.id,
            metadata={"provider": identity.provider.value},
            ip_address=ip_address,
            user_agent=user_agent,
        )

    @staticmethod
    def _account_exists() -> ConflictError:
        return ConflictError(
            AuthMessages.GOOGLE_ACCOUNT_EXISTS,
            errors=[{"code": "account_exists_sign_in_to_link"}],
        )

    @staticmethod
    def _identity_in_use() -> ConflictError:
        return ConflictError(
            AuthMessages.GOOGLE_IDENTITY_IN_USE,
            errors=[{"code": "google_identity_in_use"}],
        )
