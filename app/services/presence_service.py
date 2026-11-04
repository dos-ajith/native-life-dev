import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import UserMessages
from app.models.user import User
from app.models.user_settings_defaults import UserSettingsDefaults
from app.models.user_settings_enums import VisibilityLevel
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.chat_conversation_repository import ChatConversationRepository
from app.repositories.user_block_repository import UserBlockRepository
from app.repositories.user_follow_repository import UserFollowRepository
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.presence import PresenceRead

logger = logging.getLogger("app.presence")


class PresenceService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._users = UserRepository(db)
        self._conversations = ChatConversationRepository(db)
        self._blocks = UserBlockRepository(db)
        self._follows = UserFollowRepository(db)
        self._privacy = UserPrivacySettingsRepository(db)

    def get(self, viewer: User, target_id: UUID) -> PresenceRead:
        target = self._users.get_by_id(target_id)
        if target is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        return self.describe(viewer.id, target)

    def describe(self, viewer_id: UUID, target: User) -> PresenceRead:
        if not self._can_see(viewer_id, target):
            return PresenceRead(user_id=target.id, visible=False, is_online=None, last_seen_at=None)
        return PresenceRead(
            user_id=target.id,
            visible=True,
            is_online=self._publisher.has_connections(target.id),
            last_seen_at=target.last_seen_at,
        )

    def user_connected(self, user_id: UUID) -> None:
        self._announce(user_id)

    def user_disconnected(self, user_id: UUID) -> None:
        self._users.touch_last_seen(user_id)
        self._announce(user_id)

    def _announce(self, user_id: UUID) -> None:
        user = self._users.get_by_id(user_id)
        if user is None:
            return
        for partner_id in self._conversations.list_partner_ids(user_id):
            if not self._publisher.has_connections(partner_id):
                continue
            presence = self.describe(partner_id, user)
            if presence.visible:
                self._publish(partner_id, presence)

    def _publish(self, recipient_id: UUID, presence: PresenceRead) -> None:
        try:
            self._publisher.publish_to_user(
                recipient_id,
                RealtimeEvent(
                    type=RealtimeEventType.PRESENCE_CHANGED,
                    data=presence.model_dump(mode="json"),
                ),
            )
        except Exception:
            logger.exception("Failed to publish presence to user %s", recipient_id)

    def _can_see(self, viewer_id: UUID, target: User) -> bool:
        if self._blocks.exists_between(viewer_id, target.id):
            return False
        settings = self._privacy.get_by_user_id(target.id)
        level = (
            settings.activity_visibility if settings else UserSettingsDefaults.ACTIVITY_VISIBILITY
        )
        if level == VisibilityLevel.PUBLIC:
            return True
        if level == VisibilityLevel.FOLLOWERS:
            return self._follows.exists(viewer_id, target.id)
        return False
