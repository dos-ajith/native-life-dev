import logging
from collections.abc import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import CommunityChatMessages, CommunityMessages
from app.models.community import Community
from app.models.community_message import CommunityMessage
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_message_repository import CommunityMessageRepository
from app.repositories.community_repository import CommunityRepository
from app.schemas.community_message import CommunityMessageRead
from app.services.activity_log_service import ActivityLogService

logger = logging.getLogger("app.community_chat")


class CommunityChatService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._communities = CommunityRepository(db)
        self._members = CommunityMemberRepository(db)
        self._messages = CommunityMessageRepository(db)
        self._activity_logs = ActivityLogService(db)

    def send(
        self, community_id: UUID, actor: User, content: str, reply_to_id: UUID | None = None
    ) -> CommunityMessage:
        community = self._member_community(community_id, actor)
        if reply_to_id is not None and (
            self._messages.get_in_community(community.id, reply_to_id) is None
        ):
            raise NotFoundError(CommunityChatMessages.REPLY_NOT_FOUND)
        message = self._messages.add(
            CommunityMessage(
                community_id=community.id,
                sender_id=actor.id,
                content=content,
                reply_to_id=reply_to_id,
            )
        )
        message = self._messages.get_in_community(community.id, message.id) or message
        self._log(actor, ActivityAction.COMMUNITY_MESSAGE_SENT, message)
        self._broadcast(
            community.id,
            RealtimeEventType.COMMUNITY_MESSAGE_CREATED,
            lambda: {"message": CommunityMessageRead.from_message(message).model_dump(mode="json")},
        )
        return message

    def history(
        self, community_id: UUID, actor: User, before_id: UUID | None, limit: int
    ) -> tuple[list[CommunityMessage], bool]:
        community = self._member_community(community_id, actor)
        before = None
        if before_id is not None:
            before = self._messages.get_in_community(community.id, before_id)
            if before is None:
                raise NotFoundError(CommunityChatMessages.NOT_FOUND)
        rows = self._messages.list_older(community.id, before, limit + 1)
        return rows[:limit], len(rows) > limit

    def delete(self, community_id: UUID, message_id: UUID, actor: User) -> None:
        community = self._member_community(community_id, actor)
        message = self._messages.get_in_community(community.id, message_id)
        if message is None:
            raise NotFoundError(CommunityChatMessages.NOT_FOUND)
        if message.sender_id != actor.id and community.owner_id != actor.id:
            raise AuthorizationError(CommunityChatMessages.CANNOT_DELETE)
        self._messages.delete(message)
        self._log(actor, ActivityAction.COMMUNITY_MESSAGE_DELETED, message)
        self._broadcast(
            community.id,
            RealtimeEventType.COMMUNITY_MESSAGE_DELETED,
            lambda: {"community_id": str(community.id), "message_id": str(message_id)},
        )

    def _member_community(self, community_id: UUID, actor: User) -> Community:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        if not self._members.is_active_member(community.id, actor.id):
            raise AuthorizationError(CommunityChatMessages.MEMBERS_ONLY)
        return community

    def _broadcast(
        self,
        community_id: UUID,
        event_type: RealtimeEventType,
        build_data: Callable[[], dict[str, object]],
    ) -> None:
        try:
            data = build_data()
            for user_id in self._members.list_active_user_ids(community_id):
                if self._publisher.has_connections(user_id):
                    self._publisher.publish_to_user(
                        user_id, RealtimeEvent(type=event_type, data=data)
                    )
        except Exception:
            logger.exception("Failed to publish %s for community %s", event_type, community_id)

    def _log(self, actor: User, action: str, message: CommunityMessage) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type="community_message",
            entity_id=message.id,
            metadata={"community_id": str(message.community_id)},
        )
