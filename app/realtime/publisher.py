import asyncio
import logging
from collections.abc import Callable, Coroutine
from concurrent.futures import Future
from functools import lru_cache, partial
from typing import Any
from uuid import UUID

from app.core.messages import RealtimeMessages
from app.realtime.connection_manager import (
    CloseCode,
    ConnectionManager,
    get_connection_manager,
)
from app.realtime.events import RealtimeEvent

logger = logging.getLogger("app.realtime")


class RealtimePublisher:
    def __init__(self, manager: ConnectionManager) -> None:
        self._manager = manager
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def unbind_loop(self) -> None:
        self._loop = None

    def has_connections(self, user_id: UUID) -> bool:
        return self._manager.has_connections(user_id)

    def publish_to_user(self, user_id: UUID, event: RealtimeEvent) -> None:
        try:
            if not self._manager.has_connections(user_id):
                return
            payload = event.model_dump(mode="json")
            self._schedule(
                lambda: self._manager.send_to_user(user_id, payload),
                f"publish {event.type} to user {user_id}",
            )
        except Exception:
            logger.exception("Failed to publish %s to user %s", event.type, user_id)

    def disconnect_token(self, token_id: UUID) -> None:
        try:
            self._schedule(
                lambda: self._manager.close_token(
                    token_id, CloseCode.UNAUTHENTICATED, RealtimeMessages.TOKEN_REVOKED
                ),
                f"disconnect token {token_id}",
            )
        except Exception:
            logger.exception("Failed to disconnect token %s", token_id)

    def _schedule(
        self, operation: Callable[[], Coroutine[Any, Any, object]], description: str
    ) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            logger.debug("Realtime event loop unavailable, skipped: %s", description)
            return
        coroutine = operation()
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, loop)
        except Exception:
            coroutine.close()
            raise
        future.add_done_callback(partial(self._log_failure, description))

    @staticmethod
    def _log_failure(description: str, future: Future[object]) -> None:
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            logger.error("Realtime delivery failed: %s", description, exc_info=error)


@lru_cache
def get_realtime_publisher() -> RealtimePublisher:
    return RealtimePublisher(get_connection_manager())
