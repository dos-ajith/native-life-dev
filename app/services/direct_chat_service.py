import logging
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import DirectChatMessages, NotificationMessages, UserMessages
from app.core.storage import (
    ALLOWED_POST_IMAGE_TYPES,
    delete_private_document,
    save_direct_message_media,
)
from app.models.chat_conversation import ChatConversation
from app.models.direct_message import DirectMessage, DirectMessageMediaType
from app.models.user import User
from app.models.user_settings_defaults import UserSettingsDefaults
from app.models.user_settings_enums import MessagePermission
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.chat_conversation_repository import ChatConversationRepository
from app.repositories.direct_message_repository import DirectMessageRepository
from app.repositories.hidden_direct_message_repository import HiddenDirectMessageRepository
from app.repositories.user_block_repository import UserBlockRepository
from app.repositories.user_follow_repository import UserFollowRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository
from app.repositories.user_repository import UserRepository
from app.schemas.direct_message import ConversationRead, DeleteScope, DirectMessageRead
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
MEDIA_PUSH_BODIES = {
    DirectMessageMediaType.IMAGE: NotificationMessages.DIRECT_MESSAGE_IMAGE_PUSH_BODY,
    DirectMessageMediaType.VIDEO: NotificationMessages.DIRECT_MESSAGE_VIDEO_PUSH_BODY,
}


def _partner_id(conversation: ChatConversation, user_id: UUID) -> UUID:
    if conversation.lower_user_id == user_id:
        return conversation.higher_user_id
    return conversation.lower_user_id


def _media_type_of(content_type: str) -> DirectMessageMediaType:
    if content_type in ALLOWED_POST_IMAGE_TYPES:
        return DirectMessageMediaType.IMAGE
    return DirectMessageMediaType.VIDEO


def _push_body(message: DirectMessage) -> str:
    content = message.content
    if not content and message.media_type is not None:
        return MEDIA_PUSH_BODIES[message.media_type]
    if len(content) > PUSH_BODY_MAX_LENGTH:
        return content[:PUSH_BODY_MAX_LENGTH].rstrip() + PUSH_BODY_SUFFIX
    return content


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
        self._hidden_messages = HiddenDirectMessageRepository(db)
        self._blocks = UserBlockRepository(db)
        self._follows = UserFollowRepository(db)
        self._privacy = UserPrivacySettingsRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._presence = PresenceService(db, self._publisher)

    def send(self, recipient_id: UUID, actor: User, content: str) -> DirectMessage:
        recipient = self._recipient(recipient_id, actor)
        self._ensure_can_message(actor, recipient)
        message = self._store(actor, recipient, DirectMessage(content=content))
        self._announce(actor, recipient, message)
        return message

    def send_media(
        self,
        recipient_id: UUID,
        actor: User,
        file: UploadFile,
        caption: str | None,
        private_upload_dir: str,
    ) -> DirectMessage:
        recipient = self._recipient(recipient_id, actor)
        self._ensure_can_message(actor, recipient)
        storage_path, content_type, size_bytes = save_direct_message_media(file, private_upload_dir)
        draft = DirectMessage(
            content=(caption or "").strip(),
            media_type=_media_type_of(content_type),
            media_storage_path=storage_path,
            media_content_type=content_type,
            media_size_bytes=size_bytes,
        )
        try:
            message = self._store(actor, recipient, draft)
        except Exception:
            delete_private_document(storage_path)
            raise
        self._announce(actor, recipient, message)
        return message

    def media_file(self, message_id: UUID, actor: User) -> tuple[str, str]:
        message = self._messages.get_visible_to_participant(message_id, actor.id)
        if (
            message is None
            or message.media_storage_path is None
            or message.media_content_type is None
        ):
            raise NotFoundError(DirectChatMessages.MEDIA_NOT_FOUND)
        return message.media_storage_path, message.media_content_type

    def _store(self, actor: User, recipient: User, message: DirectMessage) -> DirectMessage:
        conversation = self._conversations.get_or_create(actor.id, recipient.id)
        message.conversation_id = conversation.id
        message.sender_id = actor.id
        return self._messages.add(message)

    def _announce(self, actor: User, recipient: User, message: DirectMessage) -> None:
        metadata = {"recipient_id": str(recipient.id)}
        if message.media_type is not None:
            metadata["media_type"] = message.media_type.value
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DIRECT_MESSAGE_SENT,
            entity_type="direct_message",
            entity_id=message.id,
            metadata=metadata,
        )
        self._publish(
            (actor.id, recipient.id),
            RealtimeEventType.DIRECT_MESSAGE_CREATED,
            {"message": DirectMessageRead.from_message(message).model_dump(mode="json")},
        )
        self._push_to_recipient(actor, recipient, message)

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
        latest = self._messages.latest_by_conversation(ids, actor.id)
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
        rows = self._messages.list_older(conversation.id, actor.id, before, limit + 1)
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

    def delete_message(
        self, partner_id: UUID, message_id: UUID, actor: User, scope: DeleteScope
    ) -> None:
        message = self._visible_message(partner_id, message_id, actor)
        if scope == DeleteScope.EVERYONE:
            self._delete_for_everyone(message, partner_id, actor)
        else:
            self._delete_for_me(message, partner_id, actor)

    def _visible_message(self, partner_id: UUID, message_id: UUID, actor: User) -> DirectMessage:
        conversation = self._conversations.get_between(actor.id, partner_id)
        message = (
            self._messages.get_visible_in_conversation(conversation.id, message_id, actor.id)
            if conversation is not None
            else None
        )
        if message is None:
            raise NotFoundError(DirectChatMessages.MESSAGE_NOT_FOUND)
        return message

    def _delete_for_everyone(self, message: DirectMessage, partner_id: UUID, actor: User) -> None:
        if message.sender_id != actor.id:
            raise AuthorizationError(DirectChatMessages.CANNOT_DELETE_FOR_EVERYONE)
        if message.deleted_at is not None:
            raise ConflictError(DirectChatMessages.ALREADY_DELETED)
        media_path = message.media_storage_path
        deleted = self._messages.delete_for_everyone(message)
        if media_path is not None:
            delete_private_document(media_path)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DIRECT_MESSAGE_DELETED_FOR_EVERYONE,
            entity_type="direct_message",
            entity_id=deleted.id,
            metadata={"recipient_id": str(partner_id)},
        )
        self._publish(
            (actor.id, partner_id),
            RealtimeEventType.DIRECT_MESSAGE_DELETED,
            {"message": DirectMessageRead.from_message(deleted).model_dump(mode="json")},
        )

    def _delete_for_me(self, message: DirectMessage, partner_id: UUID, actor: User) -> None:
        self._hidden_messages.add(message.id, actor.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DIRECT_MESSAGE_DELETED_FOR_ME,
            entity_type="direct_message",
            entity_id=message.id,
            metadata={"partner_id": str(partner_id)},
        )
        self._publish(
            (actor.id,),
            RealtimeEventType.DIRECT_MESSAGE_HIDDEN,
            {"conversation_id": str(message.conversation_id), "message_id": str(message.id)},
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

    def _push_to_recipient(self, actor: User, recipient: User, message: DirectMessage) -> None:
        if not self._push.enabled:
            return
        settings = self._notification_settings.get_by_user_id(recipient.id)
        if settings is not None and not (settings.push_enabled and settings.messages):
            return
        content = _push_body(message)
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
