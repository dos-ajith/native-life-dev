import asyncio
import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from app.api.deps import SettingsDep
from app.core.database import SessionLocal
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.core.messages import AuthMessages, RealtimeMessages
from app.core.timezone import app_now
from app.realtime.authentication import AuthenticatedSocketIdentity, WebSocketAuthenticator
from app.realtime.connection_manager import (
    CloseCode,
    Connection,
    ConnectionLimitExceededError,
    ConnectionManager,
    get_connection_manager,
)
from app.realtime.events import (
    AuthMessage,
    ClientMessage,
    ClientMessageType,
    ControlMessage,
    ServerMessageType,
    TypingMessage,
)
from app.services.direct_chat_service import DirectChatService
from app.services.presence_service import PresenceService

IDLE_TIMEOUT_PING_INTERVALS = 2

logger = logging.getLogger("app.realtime")

router = APIRouter(tags=["realtime"])


def get_websocket_authenticator(settings: SettingsDep) -> WebSocketAuthenticator:
    return WebSocketAuthenticator(settings)


ConnectionManagerDep = Annotated[ConnectionManager, Depends(get_connection_manager)]
WebSocketAuthenticatorDep = Annotated[WebSocketAuthenticator, Depends(get_websocket_authenticator)]

_AUTH_OK = ControlMessage(type=ServerMessageType.AUTH_OK).model_dump(mode="json")
_PONG = ControlMessage(type=ServerMessageType.PONG).model_dump(mode="json")


@router.websocket("/ws")
async def realtime_socket(
    websocket: WebSocket,
    settings: SettingsDep,
    manager: ConnectionManagerDep,
    authenticator: WebSocketAuthenticatorDep,
) -> None:
    await websocket.accept()
    identity = await _authenticate(websocket, authenticator, settings.ws_auth_timeout_seconds)
    if identity is None:
        return
    try:
        connection = manager.register(identity.user_id, identity.token_id, websocket)
    except ConnectionLimitExceededError:
        await _close(
            websocket, CloseCode.TOO_MANY_CONNECTIONS, RealtimeMessages.TOO_MANY_CONNECTIONS
        )
        return
    if manager.connection_count(identity.user_id) == 1:
        await run_in_threadpool(_announce, identity.user_id, True)
    try:
        if await manager.send_to_connection(connection, _AUTH_OK):
            idle_timeout = settings.ws_ping_interval_seconds * IDLE_TIMEOUT_PING_INTERVALS
            await _serve(connection, manager, identity, idle_timeout)
    finally:
        manager.unregister(connection)
        if not manager.has_connections(identity.user_id):
            await run_in_threadpool(_announce, identity.user_id, False)


def _forward_typing(user_id: UUID, typing: TypingMessage) -> None:
    try:
        with SessionLocal() as db:
            DirectChatService(db).typing(user_id, typing.user_id, typing.is_typing)
    except Exception:
        logger.exception("Failed to forward typing for user %s", user_id)


def _announce(user_id: UUID, connected: bool) -> None:
    try:
        with SessionLocal() as db:
            service = PresenceService(db)
            if connected:
                service.user_connected(user_id)
            else:
                service.user_disconnected(user_id)
    except Exception:
        logger.exception("Failed to update presence for user %s", user_id)


async def _authenticate(
    websocket: WebSocket, authenticator: WebSocketAuthenticator, timeout_seconds: float
) -> AuthenticatedSocketIdentity | None:
    try:
        raw_message = await asyncio.wait_for(websocket.receive_text(), timeout_seconds)
    except TimeoutError:
        await _close(websocket, CloseCode.UNAUTHENTICATED, RealtimeMessages.AUTH_TIMEOUT)
        return None
    except WebSocketDisconnect:
        return None
    except KeyError:
        await _close(websocket, CloseCode.UNAUTHENTICATED, RealtimeMessages.AUTH_REQUIRED)
        return None
    try:
        message = AuthMessage.model_validate_json(raw_message)
    except ValidationError:
        await _close(websocket, CloseCode.UNAUTHENTICATED, RealtimeMessages.AUTH_REQUIRED)
        return None
    try:
        return await authenticator.authenticate(message.token)
    except AuthenticationError:
        await _close(websocket, CloseCode.UNAUTHENTICATED, AuthMessages.INVALID_TOKEN)
    except AuthorizationError:
        await _close(websocket, CloseCode.FORBIDDEN, AuthMessages.ACCOUNT_INACTIVE)
    return None


async def _serve(
    connection: Connection,
    manager: ConnectionManager,
    identity: AuthenticatedSocketIdentity,
    idle_timeout_seconds: float,
) -> None:
    websocket = connection.websocket
    while True:
        seconds_until_expiry = (identity.expires_at - app_now()).total_seconds()
        if seconds_until_expiry <= 0:
            await _close(websocket, CloseCode.UNAUTHENTICATED, RealtimeMessages.TOKEN_EXPIRED)
            return
        try:
            raw_message = await asyncio.wait_for(
                websocket.receive_text(), min(idle_timeout_seconds, seconds_until_expiry)
            )
        except TimeoutError:
            if seconds_until_expiry <= idle_timeout_seconds:
                await _close(websocket, CloseCode.UNAUTHENTICATED, RealtimeMessages.TOKEN_EXPIRED)
            else:
                await _close(websocket, CloseCode.IDLE_TIMEOUT, RealtimeMessages.IDLE_TIMEOUT)
            return
        except WebSocketDisconnect:
            return
        except KeyError:
            await _close(websocket, CloseCode.POLICY_VIOLATION, RealtimeMessages.INVALID_MESSAGE)
            return
        try:
            message = ClientMessage.model_validate_json(raw_message)
        except ValidationError:
            await _close(websocket, CloseCode.POLICY_VIOLATION, RealtimeMessages.INVALID_MESSAGE)
            return
        if message.type == ClientMessageType.PING and not await manager.send_to_connection(
            connection, _PONG
        ):
            return
        if message.type == ClientMessageType.TYPING:
            try:
                typing = TypingMessage.model_validate_json(raw_message)
            except ValidationError:
                await _close(
                    websocket, CloseCode.POLICY_VIOLATION, RealtimeMessages.INVALID_MESSAGE
                )
                return
            await run_in_threadpool(_forward_typing, identity.user_id, typing)


async def _close(websocket: WebSocket, code: CloseCode, reason: str) -> None:
    try:
        await websocket.close(code=code.value, reason=reason)
    except RuntimeError:
        return
