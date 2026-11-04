from typing import Any

from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.auth import AuthenticatedResult, AuthenticatedUserRead, TokenResponse
from app.schemas.native_place import UserNativePlaceRead
from app.services.aadhaar_document_service import AadhaarDocumentService
from app.services.account_role_status_service import AccountRoleStatusService
from app.services.session_token_service import IssuedSession
from app.services.user_native_place_service import UserNativePlaceService

SECONDS_PER_MINUTE = 60


def authenticated_user(user: User, db: Session) -> AuthenticatedUserRead:
    return AuthenticatedUserRead.from_user(
        user,
        AccountRoleStatusService(db).describe(user),
        AadhaarDocumentService(db).has_document(user),
        [
            UserNativePlaceRead.from_user_native_place(item)
            for item in UserNativePlaceService(db).list_for(user)
        ],
    )


def _token_fields(session: IssuedSession, user: User, db: Session) -> dict[str, Any]:
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "access_token_expires_at": session.access_token_expires_at,
        "user": authenticated_user(user, db),
    }


def token_response(session: IssuedSession, user: User, db: Session) -> TokenResponse:
    return TokenResponse(**_token_fields(session, user, db))


def authenticated_result(session: IssuedSession, user: User, db: Session) -> AuthenticatedResult:
    return AuthenticatedResult(**_token_fields(session, user, db))


def registration_token_ttl_seconds(expire_minutes: int) -> int:
    return expire_minutes * SECONDS_PER_MINUTE
