import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.repositories.device_token_repository import DeviceTokenRepository
from app.services.push_sender import FcmPushSender, PushMessage, PushOutcome, PushSender

logger = logging.getLogger("app.push")


class PushPublisher:
    def __init__(
        self,
        sender: PushSender | None,
        session_factory: Callable[[], Session],
        worker_threads: int,
    ) -> None:
        self._sender = sender
        self._session_factory = session_factory
        self._executor = (
            ThreadPoolExecutor(max_workers=worker_threads, thread_name_prefix="push")
            if sender is not None
            else None
        )

    @property
    def enabled(self) -> bool:
        return self._sender is not None

    def publish(self, message: PushMessage) -> None:
        if self._executor is None:
            return
        try:
            self._executor.submit(self._deliver, message)
        except RuntimeError:
            logger.exception("Push queue is closed; dropping push for user %s", message.user_id)

    def shutdown(self) -> None:
        if self._executor is not None:
            self._executor.shutdown(wait=True)

    def _deliver(self, message: PushMessage) -> None:
        sender = self._sender
        if sender is None:
            return
        try:
            with self._session_factory() as db:
                devices = DeviceTokenRepository(db)
                tokens = devices.list_tokens_for_user(message.user_id)
                if not tokens:
                    return
                outcomes = sender.send(tokens, message)
                devices.delete_by_tokens(
                    [
                        token
                        for token, outcome in outcomes.items()
                        if outcome is PushOutcome.TOKEN_INVALID
                    ]
                )
        except Exception:
            logger.exception("Failed to deliver push to user %s", message.user_id)


@lru_cache
def get_push_publisher() -> PushPublisher:
    settings = get_settings()
    sender: PushSender | None = None
    if (
        settings.push_provider == "fcm"
        and settings.fcm_project_id
        and settings.fcm_service_account_file
    ):
        sender = FcmPushSender(
            settings.fcm_project_id,
            settings.fcm_service_account_file,
            settings.fcm_request_timeout_seconds,
        )
    return PushPublisher(sender, SessionLocal, settings.push_worker_threads)
