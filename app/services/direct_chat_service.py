import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import DirectChatMessages, NotificationMessages, UserMessages
from app.models.chat_conversation import ChatConversation
from app.models.direct_message import DirectMessage
from app.models.user import User
from app.models.user_settings_defaults import UserSettingsDefaults
from app.models.user_settings_enums import MessagePermission
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.chat_conversation_repository import ChatConversationRepository
from app.repositories.direct_message_repository import DirectMessageRepository
from app.repositories.user_block_repository import UserBlockRepository
from app.repositories.user_follow_repository import UserFollowRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.direct_message import ConversationRead, DirectMessageRead
from app.schemas.pagination import PaginationParams
from app.schemas.user import UserSummaryRead
from app.services.activity_log_service import ActivityLogService
from app.services.presence_service import PresenceService
from app.services.push_publisher import PushPublisher, get_push_publisher
from app.services.push_sender import PushMessage

logger = logging.getLogger("app.direct_chat")

PUSH_BODY_MAX_LENGTH = 120
PUSH_BODY_SUFFIX = "..."
PUSH_TYPE = "direct_message"


def _partner_id(conversation: ChatConversation, user_id: UUID) -> UUID:
    if conversation.lower_user_id == user_id:
        return conversation.higher_user_id
    return conversation.lower_user_id


class DirectChatService:
    def __init__(
        self,
        db: Session,
        publisher: RealtimePublisher | None = None,
        push_publisher: PushPublisher | None = None,
    ) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._push = push_publisher or get_push_publisher()
        self._notification_settings = UserNotificationSettingsRepository(db)
        self._users = UserRepository(db)
        self._conversations = ChatConversationRepository(db)
        self._messages = DirectMessageRepository(db)
        self._blocks = UserBlockRepository(db)
        self._follows = UserFollowRepository(db)
        self._privacy = UserPrivacySettingsRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._presence = PresenceService(db, self._publisher)

    def send(self, recipient_id: UUID, actor: User, content: str) -> DirectMessage:
        recipient = self._recipient(recipient_id, actor)
        self._ensure_can_message(actor, recipient)
        conversation = self._conversations.get_or_create(actor.id, recipient.id)
        message = self._messages.add(
            DirectMessage(conversation_id=conversation.id, sender_id=actor.id, content=content)
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DIRECT_MESSAGE_SENT,
            entity_type="direct_message",
            entity_id=message.id,
            metadata={"recipient_id": str(recipient.id)},
        )
        self._publish(
            (actor.id, recipient.id),
            RealtimeEventType.DIRECT_MESSAGE_CREATED,
            {"message": DirectMessageRead.from_message(message).model_dump(mode="json")},
        )
        self._push_if_offline(actor, recipient, message)
        return message

    def typing(self, actor_id: UUID, recipient_id: UUID, is_typing: bool) -> None:
        if actor_id == recipient_id or not self._publisher.has_connections(recipient_id):
            return
        actor = self._users.get_by_id(actor_id)
        recipient = self._users.get_by_id(recipient_id)
        if actor is None or recipient is None:
            return
        try:
            self._ensure_can_message(actor, recipient)
        except AuthorizationError:
            return
        self._publish(
            (recipient.id,),
            RealtimeEventType.DIRECT_MESSAGE_TYPING,
            {"user_id": str(actor.id), "is_typing": is_typing},
        )

    def list_conversations(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[ConversationRead], int]:
        conversations, total = self._conversations.list_for_user(actor.id, params)
        ids = [conversation.id for conversation in conversations]
        partners = {
            user.id: user
            for user in self._users.get_by_ids_including_deleted(
                [_partner_id(conversation, actor.id) for conversation in conversations]
            )
        }
        latest = self._messages.latest_by_conversation(ids)
        unread = self._messages.unread_counts(ids, actor.id)
        blocked = self._blocks.blocked_among(actor.id, list(partners))
        items = []
        for conversation in conversations:
            partner = partners[_partner_id(conversation, actor.id)]
            last = latest.get(conversation.id)
            items.append(
                ConversationRead(
                    id=conversation.id,
                    user=UserSummaryRead.model_validate(partner),
                    last_message=DirectMessageRead.from_message(last) if last else None,
                    unread_count=unread.get(conversation.id, 0),
                    blocked_by_me=partner.id in blocked,
                    presence=self._presence.describe(actor.id, partner),
                )
            )
        return items, total

    def history(
        self, partner_id: UUID, actor: User, before_id: UUID | None, limit: int
    ) -> tuple[list[DirectMessage], bool]:
        conversation = self._conversations.get_between(actor.id, partner_id)
        if conversation is None:
            return [], False
        before = None
        if before_id is not None:
            before = self._messages.get_in_conversation(conversation.id, before_id)
            if before is None:
                raise NotFoundError(DirectChatMessages.HISTORY_CURSOR_NOT_FOUND)
        rows = self._messages.list_older(conversation.id, before, limit + 1)
        return rows[:limit], len(rows) > limit

    def mark_read(self, partner_id: UUID, actor: User) -> None:
        conversation = self._conversations.get_between(actor.id, partner_id)
        if conversation is None:
            return
        if self._messages.mark_read(conversation.id, actor.id):
            self._publish(
                (partner_id,),
                RealtimeEventType.DIRECT_MESSAGES_READ,
                {"conversation_id": str(conversation.id), "reader_id": str(actor.id)},
            )

    def _recipient(self, recipient_id: UUID, actor: User) -> User:
        if recipient_id == actor.id:
            raise BusinessRuleError(DirectChatMessages.CANNOT_MESSAGE_SELF)
        recipient = self._users.get_by_id(recipient_id)
        if recipient is None:
            raise NotFoundError(UserMessages.NOT_FOUND)
        return recipient

    def _ensure_can_message(self, actor: User, recipient: User) -> None:
        if self._blocks.exists_between(actor.id, recipient.id):
            raise AuthorizationError(DirectChatMessages.BLOCKED)
        settings = self._privacy.get_by_user_id(recipient.id)
        allow_messages = (
            settings.allow_messages if settings else UserSettingsDefaults.ALLOW_MESSAGES
        )
        permission = settings.who_can_message if settings else UserSettingsDefaults.WHO_CAN_MESSAGE
        if not allow_messages:
            raise AuthorizationError(DirectChatMessages.MESSAGES_DISABLED)
        if permission == MessagePermission.CONNECTIONS and not self._are_connected(
            actor, recipient
        ):
            raise AuthorizationError(DirectChatMessages.CONNECTIONS_ONLY)

    def _are_connected(self, first: User, second: User) -> bool:
        return self._follows.exists(first.id, second.id) or self._follows.exists(
            second.id, first.id
        )

    def _push_if_offline(self, actor: User, recipient: User, message: DirectMessage) -> None:
        if not self._push.enabled or self._publisher.has_connections(recipient.id):
            return
        settings = self._notification_settings.get_by_user_id(recipient.id)
        if settings is not None and not (settings.push_enabled and settings.messages):
            return
        content = message.content
        if len(content) > PUSH_BODY_MAX_LENGTH:
            content = content[:PUSH_BODY_MAX_LENGTH].rstrip() + PUSH_BODY_SUFFIX
        try:
            self._push.publish(
                PushMessage(
                    user_id=recipient.id,
                    title=NotificationMessages.DIRECT_MESSAGE_PUSH_TITLE.format(
                        sender=f"{actor.first_name} {actor.last_name}"
                    ),
                    body=content,
                    data={
                        "type": PUSH_TYPE,
                        "sender_id": str(actor.id),
                        "conversation_id": str(message.conversation_id),
                        "message_id": str(message.id),
                    },
                )
            )
        except Exception:
            logger.exception("Failed to queue message push for user %s", recipient.id)

    def _publish(
        self, user_ids: tuple[UUID, ...], event_type: RealtimeEventType, data: dict[str, object]
    ) -> None:
        for user_id in user_ids:
            try:
                if self._publisher.has_connections(user_id):
                    self._publisher.publish_to_user(
                        user_id, RealtimeEvent(type=event_type, data=data)
                    )
            except Exception:
                logger.exception("Failed to publish %s to user %s", event_type, user_id)
