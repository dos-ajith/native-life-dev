import asyncio
import enum
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
from uuid import UUID

from fastapi import WebSocket

from app.core.config import get_settings

logger = logging.getLogger("app.realtime")


class CloseCode(enum.IntEnum):
    GOING_AWAY = 1001
    POLICY_VIOLATION = 1008
    UNAUTHENTICATED = 4401
    FORBIDDEN = 4403
    IDLE_TIMEOUT = 4408
    TOO_MANY_CONNECTIONS = 4429


class ConnectionLimitExceededError(Exception):
    pass


@dataclass(eq=False)
class Connection:
    websocket: WebSocket
    user_id: UUID
    token_id: UUID
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class ConnectionManager:
    def __init__(self, max_connections_per_user: int, send_timeout_seconds: float) -> None:
        self._max_connections_per_user = max_connections_per_user
        self._send_timeout_seconds = send_timeout_seconds
        self._connections_by_user: dict[UUID, set[Connection]] = {}

    def register(self, user_id: UUID, token_id: UUID, websocket: WebSocket) -> Connection:
        if self.connection_count(user_id) >= self._max_connections_per_user:
            raise ConnectionLimitExceededError
        connection = Connection(websocket=websocket, user_id=user_id, token_id=token_id)
        self._connections_by_user.setdefault(user_id, set()).add(connection)
        logger.info(
            "WebSocket connected user=%s connections=%d",
            user_id,
            self.connection_count(user_id),
        )
        return connection

    def unregister(self, connection: Connection) -> None:
        user_connections = self._connections_by_user.get(connection.user_id)
        if user_connections is None or connection not in user_connections:
            return
        user_connections.discard(connection)
        if not user_connections:
            del self._connections_by_user[connection.user_id]
        logger.info(
            "WebSocket disconnected user=%s connections=%d",
            connection.user_id,
            self.connection_count(connection.user_id),
        )

    def has_connections(self, user_id: UUID) -> bool:
        return self.connection_count(user_id) > 0

    def connection_count(self, user_id: UUID) -> int:
        return len(self._connections_by_user.get(user_id, ()))

    def total_connection_count(self) -> int:
        return sum(len(connections) for connections in self._connections_by_user.values())

    async def send_to_connection(self, connection: Connection, payload: Mapping[str, Any]) -> bool:
        try:
            async with connection.send_lock:
                await asyncio.wait_for(
                    connection.websocket.send_json(payload), self._send_timeout_seconds
                )
        except Exception:
            logger.warning(
                "WebSocket send failed, dropping connection user=%s",
                connection.user_id,
                exc_info=True,
            )
            await self._drop(connection, CloseCode.GOING_AWAY)
            return False
        return True

    async def send_to_user(self, user_id: UUID, payload: Mapping[str, Any]) -> int:
        connections = list(self._connections_by_user.get(user_id, ()))
        results = await asyncio.gather(
            *(self.send_to_connection(connection, payload) for connection in connections)
        )
        return sum(results)

    async def close_token(self, token_id: UUID, code: CloseCode, reason: str = "") -> int:
        matching = [
            connection
            for connections in self._connections_by_user.values()
            for connection in connections
            if connection.token_id == token_id
        ]
        return await self._close_connections(matching, code, reason)

    async def close_user(self, user_id: UUID, code: CloseCode, reason: str = "") -> int:
        connections = list(self._connections_by_user.get(user_id, ()))
        return await self._close_connections(connections, code, reason)

    async def close_all(self, code: CloseCode, reason: str = "") -> int:
        connections = [
            connection
            for user_connections in self._connections_by_user.values()
            for connection in user_connections
        ]
        return await self._close_connections(connections, code, reason)

    async def _close_connections(
        self, connections: Iterable[Connection], code: CloseCode, reason: str
    ) -> int:
        targets = list(connections)
        await asyncio.gather(*(self._drop(connection, code, reason) for connection in targets))
        return len(targets)

    async def _drop(self, connection: Connection, code: CloseCode, reason: str = "") -> None:
        self.unregister(connection)
        try:
            await asyncio.wait_for(
                connection.websocket.close(code=code.value, reason=reason),
                self._send_timeout_seconds,
            )
        except Exception:
            logger.debug("WebSocket close failed user=%s", connection.user_id, exc_info=True)


@lru_cache
def get_connection_manager() -> ConnectionManager:
    settings = get_settings()
    return ConnectionManager(
        max_connections_per_user=settings.ws_max_connections_per_user,
        send_timeout_seconds=settings.ws_send_timeout_seconds,
    )
