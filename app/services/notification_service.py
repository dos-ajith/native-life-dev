from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import NotificationMessages
from app.models.notification import Notification, NotificationType
from app.models.post import Post
from app.models.user import User
from app.models.user_notification_settings import UserNotificationSettings
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.notification import NotificationRead, NotificationTargetRead
from app.schemas.pagination import PaginationParams
from app.services.post_service import PostService


class NotificationService:
    def __init__(self, db: Session) -> None:
        self._notifications = NotificationRepository(db)
        self._settings = UserNotificationSettingsRepository(db)
        self._users = UserRepository(db)
        self._posts = PostService(db)

    def notify_user_followed(self, follower: User, followed_id: UUID) -> None:
        self._create_if_enabled(
            recipient_id=followed_id,
            actor_id=follower.id,
            type_=NotificationType.USER_FOLLOWED,
            entity_type="user",
            entity_id=follower.id,
            is_enabled=lambda settings: settings.followers,
        )

    def notify_post_liked(self, post: Post, actor: User) -> None:
        self._create_if_enabled(
            recipient_id=post.user_id,
            actor_id=actor.id,
            type_=NotificationType.POST_LIKED,
            entity_type="post",
            entity_id=post.id,
            is_enabled=lambda settings: settings.likes,
        )

    def notify_post_commented(self, post: Post, actor: User, comment_id: UUID) -> None:
        self._create_if_enabled(
            recipient_id=post.user_id,
            actor_id=actor.id,
            type_=NotificationType.POST_COMMENTED,
            entity_type="post",
            entity_id=post.id,
            is_enabled=lambda settings: settings.comments,
            metadata={"comment_id": str(comment_id)},
        )

    def list_notifications(
        self, recipient: User, params: PaginationParams, unread_only: bool
    ) -> tuple[list[NotificationRead], int]:
        notifications, total = self._notifications.list_for_recipient(
            recipient.id, params, unread_only
        )
        return [self._to_read(notification, recipient) for notification in notifications], total

    def get_unread_count(self, recipient: User) -> int:
        return self._notifications.count_unread(recipient.id)

    def mark_notification_read(self, recipient: User, notification_id: UUID) -> NotificationRead:
        notification = self._get_owned(notification_id, recipient.id)
        updated = self._notifications.mark_read(notification)
        return self._to_read(updated, recipient)

    def mark_all_notifications_read(self, recipient: User) -> None:
        self._notifications.mark_all_read(recipient.id)

    def _get_owned(self, notification_id: UUID, recipient_id: UUID) -> Notification:
        notification = self._notifications.get_by_id_for_recipient(notification_id, recipient_id)
        if notification is None:
            raise NotFoundError(NotificationMessages.NOT_FOUND)
        return notification

    def _create_if_enabled(
        self,
        *,
        recipient_id: UUID,
        actor_id: UUID,
        type_: NotificationType,
        entity_type: str,
        entity_id: UUID,
        is_enabled: Callable[[UserNotificationSettings], bool],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if recipient_id == actor_id:
            return
        settings = self._get_or_create_settings(recipient_id)
        if not is_enabled(settings):
            return
        self._notifications.add(
            Notification(
                recipient_id=recipient_id,
                actor_id=actor_id,
                type=type_,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_=metadata,
            )
        )

    def _get_or_create_settings(self, user_id: UUID) -> UserNotificationSettings:
        settings = self._settings.get_by_user_id(user_id)
        if settings is not None:
            return settings
        return self._settings.add(UserNotificationSettings(user_id=user_id))

    def _to_read(self, notification: Notification, recipient: User) -> NotificationRead:
        actor = self._resolve_actor(notification.actor_id)
        target = self._resolve_target(notification, recipient)
        return NotificationRead.from_notification(notification, actor, target)

    def _resolve_actor(self, actor_id: UUID | None) -> User | None:
        if actor_id is None:
            return None
        return self._users.get_by_id_including_deleted(actor_id)

    def _resolve_target(
        self, notification: Notification, recipient: User
    ) -> NotificationTargetRead | None:
        if notification.entity_type is None or notification.entity_id is None:
            return None
        if notification.entity_type == "post":
            try:
                post = self._posts.get_visible(notification.entity_id, recipient)
            except NotFoundError:
                return None
            return NotificationTargetRead(type="post", id=post.id)
        if notification.entity_type == "user":
            return NotificationTargetRead(type="user", id=notification.entity_id)
        return None
