from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import NotificationMessages
from app.core.permissions import PermissionName, RoleSlug
from app.models.notification import Notification, NotificationType
from app.models.post import Post
from app.models.user import User
from app.models.user_notification_settings import UserNotificationSettings
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.notification import NotificationRead
from app.schemas.pagination import PaginationParams

ROLE_UPGRADE_REQUEST_ENTITY_TYPE = "role_upgrade_request"
ROLE_NAME_METADATA_KEY = "role_name"

NOTIFICATION_MESSAGE_TEMPLATES = {
    NotificationType.USER_FOLLOWED: NotificationMessages.USER_FOLLOWED,
    NotificationType.FOLLOW_REQUESTED: NotificationMessages.FOLLOW_REQUESTED,
    NotificationType.FOLLOW_REQUEST_ACCEPTED: NotificationMessages.FOLLOW_REQUEST_ACCEPTED,
    NotificationType.POST_LIKED: NotificationMessages.POST_LIKED,
    NotificationType.POST_COMMENTED: NotificationMessages.POST_COMMENTED,
    NotificationType.ROLE_UPGRADE_REQUESTED: NotificationMessages.ROLE_UPGRADE_REQUESTED,
    NotificationType.ROLE_UPGRADE_APPROVED: NotificationMessages.ROLE_UPGRADE_APPROVED,
    NotificationType.ROLE_UPGRADE_REJECTED: NotificationMessages.ROLE_UPGRADE_REJECTED,
}


class NotificationService:
    def __init__(self, db: Session) -> None:
        self._notifications = NotificationRepository(db)
        self._settings = UserNotificationSettingsRepository(db)
        self._users = UserRepository(db)

    def notify_user_followed(self, follower: User, followed_id: UUID) -> None:
        self._create_if_enabled(
            recipient_id=followed_id,
            actor_id=follower.id,
            type_=NotificationType.USER_FOLLOWED,
            entity_type="user",
            entity_id=follower.id,
            is_enabled=lambda settings: settings.followers,
        )

    def notify_follow_requested(self, requester: User, target_id: UUID) -> None:
        self._create_if_enabled(
            recipient_id=target_id,
            actor_id=requester.id,
            type_=NotificationType.FOLLOW_REQUESTED,
            entity_type="user",
            entity_id=requester.id,
            is_enabled=lambda settings: settings.followers,
        )

    def notify_follow_request_accepted(self, target: User, requester_id: UUID) -> None:
        self._create_if_enabled(
            recipient_id=requester_id,
            actor_id=target.id,
            type_=NotificationType.FOLLOW_REQUEST_ACCEPTED,
            entity_type="user",
            entity_id=target.id,
            is_enabled=lambda settings: settings.followers,
        )

    def notify_role_upgrade_requested(
        self, actor: User, request_id: UUID, role_name: str
    ) -> None:
        reviewers = self._users.list_active_with_permission(
            PermissionName.ROLE_UPGRADE_REQUEST_APPROVE, frozenset({RoleSlug.SUPER_ADMIN})
        )
        for reviewer in reviewers:
            self._create_if_enabled(
                recipient_id=reviewer.id,
                actor_id=actor.id,
                type_=NotificationType.ROLE_UPGRADE_REQUESTED,
                entity_type=ROLE_UPGRADE_REQUEST_ENTITY_TYPE,
                entity_id=request_id,
                is_enabled=lambda settings: settings.system_updates,
                metadata={ROLE_NAME_METADATA_KEY: role_name},
            )

    def notify_role_upgrade_approved(
        self, recipient_id: UUID, actor: User, request_id: UUID, role_name: str
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.ROLE_UPGRADE_APPROVED,
            entity_type=ROLE_UPGRADE_REQUEST_ENTITY_TYPE,
            entity_id=request_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={ROLE_NAME_METADATA_KEY: role_name},
        )

    def notify_role_upgrade_rejected(
        self, recipient_id: UUID, actor: User, request_id: UUID, role_name: str
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.ROLE_UPGRADE_REJECTED,
            entity_type=ROLE_UPGRADE_REQUEST_ENTITY_TYPE,
            entity_id=request_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={ROLE_NAME_METADATA_KEY: role_name},
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
        return [self._to_read(notification) for notification in notifications], total

    def get_unread_count(self, recipient: User) -> int:
        return self._notifications.count_unread(recipient.id)

    def mark_notification_read(self, recipient: User, notification_id: UUID) -> NotificationRead:
        notification = self._get_owned(notification_id, recipient.id)
        updated = self._notifications.mark_read(notification)
        return self._to_read(updated)

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

    def _to_read(self, notification: Notification) -> NotificationRead:
        return NotificationRead(
            id=notification.id,
            message=self._render_message(notification),
            is_read=notification.is_read,
            created_at=notification.created_at,
        )

    def _render_message(self, notification: Notification) -> str:
        return NOTIFICATION_MESSAGE_TEMPLATES[notification.type].format(
            actor=self._actor_name(notification.actor_id),
            role_name=(notification.metadata_ or {}).get(ROLE_NAME_METADATA_KEY, ""),
        )

    def _actor_name(self, actor_id: UUID | None) -> str:
        if actor_id is None:
            return NotificationMessages.UNKNOWN_ACTOR
        actor = self._users.get_by_id_including_deleted(actor_id)
        if actor is None:
            return NotificationMessages.UNKNOWN_ACTOR
        return f"{actor.first_name} {actor.last_name}"
