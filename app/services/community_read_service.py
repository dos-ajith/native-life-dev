import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import CommunityMessages
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_repository import CommunityRepository

logger = logging.getLogger("app.community_read")


class CommunityReadService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)

    def mark_read(self, community_id: UUID, actor: User) -> None:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        if not self._members.is_active_member(community.id, actor.id):
            raise AuthorizationError(CommunityMessages.NOT_A_MEMBER)
        self._members.mark_read(community.id, actor.id)
        self._publish_read(community.id, actor.id)

    def _publish_read(self, community_id: UUID, user_id: UUID) -> None:
        try:
            if self._publisher.has_connections(user_id):
                self._publisher.publish_to_user(
                    user_id,
                    RealtimeEvent(
                        type=RealtimeEventType.COMMUNITY_READ,
                        data={"community_id": str(community_id), "unread_count": 0},
                    ),
                )
        except Exception:
            logger.exception("Failed to publish read state for community %s", community_id)
