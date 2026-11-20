import enum
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.core.config import Settings
from app.core.exceptions import AuthenticationError
from app.core.messages import AIMessages, AuthMessages
from app.core.timezone import app_now, get_app_timezone

TOKEN_TYPE_CLAIM = "typ"
ACCESS_TOKEN_TYPE = "access"
AI_SPEECH_TOKEN_TYPE = "ai_speech"


class RegistrationTokenType(enum.StrEnum):
    PHONE = "phone_registration"
    GOOGLE = "google_registration"


@dataclass
class TokenClaims:
    user_id: UUID
    jti: UUID
    expires_at: datetime


@dataclass(frozen=True)
class SpeechTokenClaims:
    user_id: UUID
    text: str
    avatar_id: str


@dataclass
class IssuedToken:
    token: str
    jti: UUID
    expires_at: datetime


def create_access_token(user_id: UUID, settings: Settings) -> IssuedToken:
    now = app_now()
    jti = uuid4()
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "iat": now,
        "exp": expires_at,
        TOKEN_TYPE_CLAIM: ACCESS_TOKEN_TYPE,
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return IssuedToken(token=token, jti=jti, expires_at=expires_at)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def parse_token_claims(token: str, settings: Settings) -> TokenClaims:
    try:
        payload = decode_access_token(token, settings)
        if payload.get(TOKEN_TYPE_CLAIM, ACCESS_TOKEN_TYPE) != ACCESS_TOKEN_TYPE:
            raise AuthenticationError(AuthMessages.INVALID_TOKEN)
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            jti=UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=get_app_timezone()),
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AuthenticationError(AuthMessages.INVALID_TOKEN) from exc


def create_registration_token(
    token_type: RegistrationTokenType,
    subject: str,
    settings: Settings,
    extra_claims: dict[str, str] | None = None,
) -> str:
    now = app_now()
    payload: dict[str, Any] = {
        **(extra_claims or {}),
        "sub": subject,
        "jti": str(uuid4()),
        "iat": now,
        "exp": now + timedelta(minutes=settings.registration_token_expire_minutes),
        TOKEN_TYPE_CLAIM: token_type.value,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def parse_registration_token(
    token: str, token_type: RegistrationTokenType, settings: Settings
) -> dict[str, Any]:
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError as exc:
        raise AuthenticationError(AuthMessages.INVALID_REGISTRATION_TOKEN) from exc
    if payload.get(TOKEN_TYPE_CLAIM) != token_type.value or not payload.get("sub"):
        raise AuthenticationError(AuthMessages.INVALID_REGISTRATION_TOKEN)
    return payload


def create_speech_token(user_id: UUID, text: str, avatar_id: str, settings: Settings) -> str:
    now = app_now()
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "txt": text,
        "avt": avatar_id,
        "iat": now,
        "exp": now + timedelta(seconds=settings.ai_speech_token_expire_seconds),
        TOKEN_TYPE_CLAIM: AI_SPEECH_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def parse_speech_token(token: str, settings: Settings) -> SpeechTokenClaims:
    try:
        payload = decode_access_token(token, settings)
        if payload.get(TOKEN_TYPE_CLAIM) != AI_SPEECH_TOKEN_TYPE:
            raise AuthenticationError(AIMessages.SPEECH_LINK_INVALID)
        return SpeechTokenClaims(
            user_id=UUID(payload["sub"]), text=str(payload["txt"]), avatar_id=str(payload["avt"])
        )
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise AuthenticationError(AIMessages.SPEECH_LINK_INVALID) from exc
