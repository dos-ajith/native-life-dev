from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import Request
from google.auth.transport.requests import Request as RequestsTransport
from google.oauth2 import id_token

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, ServiceUnavailableError
from app.core.messages import AuthMessages

CLOCK_SKEW_SECONDS = 10
VERIFIED_EMAIL_VALUES = (True, "true")

verify_google_id_token: Callable[..., dict[str, Any]] = id_token.verify_oauth2_token


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str | None
    email_verified: bool
    given_name: str | None
    family_name: str | None


class GoogleTokenVerifier(Protocol):
    def verify(self, token: str) -> GoogleIdentity: ...


def invalid_google_token() -> AuthenticationError:
    return AuthenticationError(
        AuthMessages.GOOGLE_TOKEN_INVALID, errors=[{"code": "google_token_invalid"}]
    )


class GoogleIdTokenVerifier:
    def __init__(self, client_ids: Sequence[str], transport: Request | None = None) -> None:
        self._client_ids = list(client_ids)
        self._transport = transport or RequestsTransport()

    def verify(self, token: str) -> GoogleIdentity:
        try:
            claims = verify_google_id_token(
                token,
                self._transport,
                audience=self._client_ids,
                clock_skew_in_seconds=CLOCK_SKEW_SECONDS,
            )
        except TransportError as exc:
            raise ServiceUnavailableError(
                AuthMessages.GOOGLE_UNAVAILABLE, errors=[{"code": "google_unavailable"}]
            ) from exc
        except (ValueError, GoogleAuthError) as exc:
            raise invalid_google_token() from exc
        subject = claims.get("sub")
        if claims.get("aud") not in self._client_ids or not isinstance(subject, str) or not subject:
            raise invalid_google_token()
        return GoogleIdentity(
            subject=subject,
            email=claims.get("email"),
            email_verified=claims.get("email_verified") in VERIFIED_EMAIL_VALUES,
            given_name=claims.get("given_name"),
            family_name=claims.get("family_name"),
        )


def get_google_token_verifier(settings: Settings) -> GoogleTokenVerifier | None:
    if not settings.google_client_ids:
        return None
    return GoogleIdTokenVerifier(settings.google_client_ids)
