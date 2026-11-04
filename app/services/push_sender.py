import enum
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

logger = logging.getLogger("app.push")

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
FCM_SEND_URL = "https://fcm.googleapis.com/v1/projects/{project_id}/messages:send"
UNREGISTERED_ERROR_CODE = "UNREGISTERED"
HTTP_NOT_FOUND = 404
ANDROID_PRIORITY = "HIGH"
APNS_PRIORITY_HEADERS = {"apns-priority": "10"}

load_service_account_credentials: Callable[..., Any] = (
    service_account.Credentials.from_service_account_file
)
open_authorized_session: Callable[..., Any] = AuthorizedSession


class PushOutcome(enum.Enum):
    DELIVERED = "delivered"
    TOKEN_INVALID = "token_invalid"
    FAILED = "failed"


@dataclass(frozen=True)
class PushMessage:
    user_id: UUID
    title: str
    body: str
    data: dict[str, str]


class PushSender(Protocol):
    def send(self, tokens: Sequence[str], message: PushMessage) -> dict[str, PushOutcome]: ...


class FcmPushSender:
    def __init__(self, project_id: str, service_account_file: str, timeout_seconds: float) -> None:
        self._credentials = load_service_account_credentials(
            service_account_file, scopes=[FCM_SCOPE]
        )
        self._url = FCM_SEND_URL.format(project_id=project_id)
        self._timeout_seconds = timeout_seconds

    def send(self, tokens: Sequence[str], message: PushMessage) -> dict[str, PushOutcome]:
        session = open_authorized_session(self._credentials)
        try:
            return {token: self._send_one(session, token, message) for token in tokens}
        finally:
            session.close()

    def _send_one(self, session: Any, token: str, message: PushMessage) -> PushOutcome:
        try:
            response = session.post(
                self._url, json=_build_payload(token, message), timeout=self._timeout_seconds
            )
        except (requests.RequestException, GoogleAuthError):
            logger.exception("FCM request failed for user %s", message.user_id)
            return PushOutcome.FAILED
        if response.ok:
            return PushOutcome.DELIVERED
        if _is_unregistered(response):
            return PushOutcome.TOKEN_INVALID
        logger.warning(
            "FCM rejected a push for user %s: HTTP %s %s",
            message.user_id,
            response.status_code,
            _error_status(response),
        )
        return PushOutcome.FAILED


def _build_payload(token: str, message: PushMessage) -> dict[str, Any]:
    return {
        "message": {
            "token": token,
            "notification": {"title": message.title, "body": message.body},
            "data": message.data,
            "android": {"priority": ANDROID_PRIORITY},
            "apns": {"headers": APNS_PRIORITY_HEADERS},
        }
    }


def _error_body(response: requests.Response) -> dict[str, Any]:
    try:
        error = response.json().get("error")
    except ValueError:
        return {}
    return error if isinstance(error, dict) else {}


def _error_status(response: requests.Response) -> str:
    return str(_error_body(response).get("status", ""))


def _is_unregistered(response: requests.Response) -> bool:
    if response.status_code == HTTP_NOT_FOUND:
        return True
    details = _error_body(response).get("details", [])
    return any(
        isinstance(detail, dict) and detail.get("errorCode") == UNREGISTERED_ERROR_CODE
        for detail in details
    )
