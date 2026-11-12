import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import NotificationMessages
from app.core.permissions import PROMOTER_REVIEW_ROLE_SLUGS, PermissionName, RoleSlug
from app.models.notification import Notification, NotificationType
from app.models.post import Post
from app.models.user import User
from app.models.user_notification_settings import UserNotificationSettings
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_notification_settings_repository import (
    UserNotificationSettingsRepository,
)
from app.repositories.user_repository import UserRepository
from app.schemas.notification import NotificationRead
from app.schemas.pagination import PaginationParams
from app.services.authorization_service import is_super_admin
from app.services.push_publisher import PushPublisher, get_push_publisher
from app.services.push_sender import PushMessage

logger = logging.getLogger("app.notification")

ROLE_UPGRADE_REQUEST_ENTITY_TYPE = "role_upgrade_request"
ROLE_NAME_METADATA_KEY = "role_name"
CATEGORY_ENTITY_TYPE = "category"
CATEGORY_NAME_METADATA_KEY = "category_name"
REVIEW_NOTE_METADATA_KEY = "review_note"
COMMUNITY_ENTITY_TYPE = "community"
COMMUNITY_NAME_METADATA_KEY = "community_name"
BUSINESS_ENTITY_TYPE = "business"
BUSINESS_NAME_METADATA_KEY = "business_name"
DEAL_ENTITY_TYPE = "deal"
DEAL_NAME_METADATA_KEY = "deal_name"
DELIVERY_ENTITY_TYPE = "delivery_request"
ORDER_NUMBER_METADATA_KEY = "order_number"
LOST_FOUND_ENTITY_TYPE = "lost_found_item"
LOST_ITEM_KIND = "lost"
ITEM_TITLE_METADATA_KEY = "item_title"
ITEM_KIND_METADATA_KEY = "item_kind"
RESPONSE_NOTE_METADATA_KEY = "response_note"
PUSH_NOTIFICATION_ID_KEY = "notification_id"
PUSH_TYPE_KEY = "type"
PUSH_ENTITY_TYPE_KEY = "entity_type"
PUSH_ENTITY_ID_KEY = "entity_id"
LOST_FOUND_RESPONSE_TYPES = (
    NotificationType.LOST_FOUND_FOUND,
    NotificationType.LOST_FOUND_CLAIMED,
)

NOTIFICATION_MESSAGE_TEMPLATES = {
    NotificationType.USER_FOLLOWED: NotificationMessages.USER_FOLLOWED,
    NotificationType.FOLLOW_REQUESTED: NotificationMessages.FOLLOW_REQUESTED,
    NotificationType.FOLLOW_REQUEST_ACCEPTED: NotificationMessages.FOLLOW_REQUEST_ACCEPTED,
    NotificationType.POST_LIKED: NotificationMessages.POST_LIKED,
    NotificationType.POST_COMMENTED: NotificationMessages.POST_COMMENTED,
    NotificationType.ROLE_UPGRADE_REQUESTED: NotificationMessages.ROLE_UPGRADE_REQUESTED,
    NotificationType.ROLE_UPGRADE_APPROVED: NotificationMessages.ROLE_UPGRADE_APPROVED,
    NotificationType.ROLE_UPGRADE_REJECTED: NotificationMessages.ROLE_UPGRADE_REJECTED,
    NotificationType.CATEGORY_SUGGESTED: NotificationMessages.CATEGORY_SUGGESTED,
    NotificationType.CATEGORY_APPROVED: NotificationMessages.CATEGORY_APPROVED,
    NotificationType.CATEGORY_REJECTED: NotificationMessages.CATEGORY_REJECTED,
    NotificationType.BUSINESS_SUBMITTED: NotificationMessages.BUSINESS_SUBMITTED,
    NotificationType.BUSINESS_APPROVED: NotificationMessages.BUSINESS_APPROVED,
    NotificationType.BUSINESS_REJECTED: NotificationMessages.BUSINESS_REJECTED,
    NotificationType.COMMUNITY_SUBMITTED: NotificationMessages.COMMUNITY_SUBMITTED,
    NotificationType.COMMUNITY_APPROVED: NotificationMessages.COMMUNITY_APPROVED,
    NotificationType.COMMUNITY_REJECTED: NotificationMessages.COMMUNITY_REJECTED,
    NotificationType.COMMUNITY_JOIN_REQUESTED: NotificationMessages.COMMUNITY_JOIN_REQUESTED,
    NotificationType.COMMUNITY_JOIN_APPROVED: NotificationMessages.COMMUNITY_JOIN_APPROVED,
    NotificationType.COMMUNITY_JOIN_REJECTED: NotificationMessages.COMMUNITY_JOIN_REJECTED,
    NotificationType.COMMUNITY_POST_REMOVED: NotificationMessages.COMMUNITY_POST_REMOVED,
    NotificationType.DEAL_ACCEPTANCE_REQUESTED: NotificationMessages.DEAL_ACCEPTANCE_REQUESTED,
    NotificationType.DEAL_NO_ELIGIBLE_ACCEPTORS: NotificationMessages.DEAL_NO_ELIGIBLE_ACCEPTORS,
    NotificationType.DEAL_NO_ELIGIBLE_ACCEPTORS_ADMIN: (
        NotificationMessages.DEAL_NO_ELIGIBLE_ACCEPTORS_ADMIN
    ),
    NotificationType.DEAL_PUBLISHED: NotificationMessages.DEAL_PUBLISHED,
    NotificationType.DEAL_EXPIRED: NotificationMessages.DEAL_EXPIRED,
    NotificationType.DEAL_PROMOTED_FOR_BUSINESS: NotificationMessages.DEAL_PROMOTED_FOR_BUSINESS,
    NotificationType.DEAL_REPUBLISH_REQUESTED: NotificationMessages.DEAL_REPUBLISH_REQUESTED,
    NotificationType.DEAL_BLOCKED: NotificationMessages.DEAL_BLOCKED,
    NotificationType.DEAL_REPUBLISH_APPROVED: NotificationMessages.DEAL_REPUBLISH_APPROVED,
    NotificationType.DEAL_REPUBLISH_REJECTED: NotificationMessages.DEAL_REPUBLISH_REJECTED,
    NotificationType.DELIVERY_REQUESTED: NotificationMessages.DELIVERY_REQUESTED,
    NotificationType.DELIVERY_ACCEPTED: NotificationMessages.DELIVERY_ACCEPTED,
    NotificationType.DELIVERY_REJECTED: NotificationMessages.DELIVERY_REJECTED,
    NotificationType.DELIVERY_EXPIRED: NotificationMessages.DELIVERY_EXPIRED,
    NotificationType.LOST_FOUND_NEARBY: NotificationMessages.LOST_FOUND_NEARBY,
    NotificationType.LOST_FOUND_RESOLVED: NotificationMessages.LOST_FOUND_RESOLVED,
    NotificationType.LOST_FOUND_FOUND: NotificationMessages.LOST_FOUND_FOUND,
    NotificationType.LOST_FOUND_CLAIMED: NotificationMessages.LOST_FOUND_CLAIMED,
    NotificationType.LOST_FOUND_CLOSED: NotificationMessages.LOST_FOUND_CLOSED,
}


class NotificationService:
    def __init__(
        self,
        db: Session,
        publisher: RealtimePublisher | None = None,
        push_publisher: PushPublisher | None = None,
    ) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._push = push_publisher or get_push_publisher()
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
        self, actor: User, request_id: UUID, role_name: str, role_slug: str
    ) -> list[User]:
        reviewer_permissions = [PermissionName.ROLE_UPGRADE_REQUEST_APPROVE]
        if role_slug in PROMOTER_REVIEW_ROLE_SLUGS:
            reviewer_permissions.append(PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER)
        reviewers = self._users.list_active_with_permission(
            reviewer_permissions, frozenset({RoleSlug.SUPER_ADMIN})
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
        return reviewers

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

    def notify_category_suggested(
        self, actor: User, category_id: UUID, category_name: str
    ) -> list[User]:
        reviewers = self._users.list_active_with_permission(
            [PermissionName.CATEGORY_APPROVE], frozenset({RoleSlug.SUPER_ADMIN})
        )
        for reviewer in reviewers:
            self._create_if_enabled(
                recipient_id=reviewer.id,
                actor_id=actor.id,
                type_=NotificationType.CATEGORY_SUGGESTED,
                entity_type=CATEGORY_ENTITY_TYPE,
                entity_id=category_id,
                is_enabled=lambda settings: settings.system_updates,
                metadata={CATEGORY_NAME_METADATA_KEY: category_name},
            )
        return reviewers

    def notify_category_approved(
        self, recipient_id: UUID, actor: User, category_id: UUID, category_name: str
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.CATEGORY_APPROVED,
            entity_type=CATEGORY_ENTITY_TYPE,
            entity_id=category_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={CATEGORY_NAME_METADATA_KEY: category_name},
        )

    def notify_category_rejected(
        self,
        recipient_id: UUID,
        actor: User,
        category_id: UUID,
        category_name: str,
        review_note: str,
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.CATEGORY_REJECTED,
            entity_type=CATEGORY_ENTITY_TYPE,
            entity_id=category_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={
                CATEGORY_NAME_METADATA_KEY: category_name,
                REVIEW_NOTE_METADATA_KEY: review_note,
            },
        )

    def notify_business_submitted(
        self,
        actor: User,
        business_id: UUID,
        business_name: str,
        native_admin_id: UUID | None,
    ) -> list[User]:
        candidates = self._users.list_active_with_permission(
            [PermissionName.BUSINESS_REVIEW], frozenset({RoleSlug.SUPER_ADMIN})
        )
        reviewers = [
            user for user in candidates if is_super_admin(user) or user.id == native_admin_id
        ]
        for reviewer in reviewers:
            self._create_if_enabled(
                recipient_id=reviewer.id,
                actor_id=actor.id,
                type_=NotificationType.BUSINESS_SUBMITTED,
                entity_type=BUSINESS_ENTITY_TYPE,
                entity_id=business_id,
                is_enabled=lambda settings: settings.system_updates,
                metadata={BUSINESS_NAME_METADATA_KEY: business_name},
            )
        return reviewers

    def notify_business_approved(
        self, recipient_id: UUID, actor: User, business_id: UUID, business_name: str
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.BUSINESS_APPROVED,
            entity_type=BUSINESS_ENTITY_TYPE,
            entity_id=business_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={BUSINESS_NAME_METADATA_KEY: business_name},
        )

    def notify_business_rejected(
        self,
        recipient_id: UUID,
        actor: User,
        business_id: UUID,
        business_name: str,
        review_note: str,
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=NotificationType.BUSINESS_REJECTED,
            entity_type=BUSINESS_ENTITY_TYPE,
            entity_id=business_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={
                BUSINESS_NAME_METADATA_KEY: business_name,
                REVIEW_NOTE_METADATA_KEY: review_note,
            },
        )

    def notify_community_submitted(
        self, actor: User, community_id: UUID, community_name: str
    ) -> list[User]:
        reviewers = self._users.list_active_with_permission(
            [PermissionName.COMMUNITY_APPROVE], frozenset({RoleSlug.SUPER_ADMIN})
        )
        for reviewer in reviewers:
            self._notify_community(
                reviewer.id,
                actor,
                NotificationType.COMMUNITY_SUBMITTED,
                community_id,
                community_name,
            )
        return reviewers

    def notify_community_reviewed(
        self,
        recipient_id: UUID,
        actor: User,
        community_id: UUID,
        community_name: str,
        review_note: str | None,
    ) -> None:
        type_ = (
            NotificationType.COMMUNITY_REJECTED
            if review_note is not None
            else NotificationType.COMMUNITY_APPROVED
        )
        self._notify_community(
            recipient_id, actor, type_, community_id, community_name, review_note
        )

    def notify_community_join_requested(
        self, owner_id: UUID, actor: User, community_id: UUID, community_name: str
    ) -> None:
        self._notify_community(
            owner_id,
            actor,
            NotificationType.COMMUNITY_JOIN_REQUESTED,
            community_id,
            community_name,
        )

    def notify_community_join_decided(
        self,
        recipient_id: UUID,
        actor: User,
        community_id: UUID,
        community_name: str,
        approved: bool,
    ) -> None:
        type_ = (
            NotificationType.COMMUNITY_JOIN_APPROVED
            if approved
            else NotificationType.COMMUNITY_JOIN_REJECTED
        )
        self._notify_community(recipient_id, actor, type_, community_id, community_name)

    def notify_community_post_removed(
        self, recipient_id: UUID, actor: User, community_id: UUID, community_name: str, reason: str
    ) -> None:
        self._notify_community(
            recipient_id,
            actor,
            NotificationType.COMMUNITY_POST_REMOVED,
            community_id,
            community_name,
            reason,
        )

    def _notify_community(
        self,
        recipient_id: UUID,
        actor: User,
        type_: NotificationType,
        community_id: UUID,
        community_name: str,
        review_note: str | None = None,
    ) -> None:
        metadata: dict[str, Any] = {COMMUNITY_NAME_METADATA_KEY: community_name}
        if review_note is not None:
            metadata[REVIEW_NOTE_METADATA_KEY] = review_note
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=type_,
            entity_type=COMMUNITY_ENTITY_TYPE,
            entity_id=community_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata=metadata,
        )

    def notify_deal_acceptance_requested(
        self, recipient_id: UUID, actor: User, deal_id: UUID, deal_name: str
    ) -> None:
        self._notify_deal(
            recipient_id, actor.id, NotificationType.DEAL_ACCEPTANCE_REQUESTED, deal_id, deal_name
        )

    def notify_deal_no_eligible_acceptors(
        self, creator_id: UUID, deal_id: UUID, deal_name: str
    ) -> None:
        self._notify_deal(
            creator_id, None, NotificationType.DEAL_NO_ELIGIBLE_ACCEPTORS, deal_id, deal_name
        )

    def notify_admins_deal_no_eligible_acceptors(
        self, actor: User, deal_id: UUID, deal_name: str
    ) -> list[User]:
        admins = self._users.list_active_with_permission(
            [PermissionName.DEAL_VIEW_ANY], frozenset({RoleSlug.SUPER_ADMIN})
        )
        for admin in admins:
            self._notify_deal(
                admin.id,
                actor.id,
                NotificationType.DEAL_NO_ELIGIBLE_ACCEPTORS_ADMIN,
                deal_id,
                deal_name,
            )
        return admins

    def notify_deal_published(
        self, creator_id: UUID, actor: User, deal_id: UUID, deal_name: str
    ) -> None:
        self._notify_deal(creator_id, actor.id, NotificationType.DEAL_PUBLISHED, deal_id, deal_name)

    def notify_deal_event(
        self,
        recipient_id: UUID,
        actor: User,
        type_: NotificationType,
        deal_id: UUID,
        deal_name: str,
    ) -> None:
        self._notify_deal(recipient_id, actor.id, type_, deal_id, deal_name)

    def notify_deal_expired(self, creator_id: UUID, deal_id: UUID, deal_name: str) -> None:
        self._notify_deal(creator_id, None, NotificationType.DEAL_EXPIRED, deal_id, deal_name)

    def _notify_deal(
        self,
        recipient_id: UUID,
        actor_id: UUID | None,
        type_: NotificationType,
        deal_id: UUID,
        deal_name: str,
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type_=type_,
            entity_type=DEAL_ENTITY_TYPE,
            entity_id=deal_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={DEAL_NAME_METADATA_KEY: deal_name},
        )

    def notify_delivery(
        self,
        recipient_id: UUID,
        actor_id: UUID | None,
        type_: NotificationType,
        request_id: UUID,
        order_number: str,
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor_id,
            type_=type_,
            entity_type=DELIVERY_ENTITY_TYPE,
            entity_id=request_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={ORDER_NUMBER_METADATA_KEY: order_number},
        )

    def notify_lost_found_nearby(
        self, recipient_id: UUID, actor: User, item_id: UUID, item_title: str, item_kind: str
    ) -> None:
        self._notify_lost_found(
            recipient_id, actor, NotificationType.LOST_FOUND_NEARBY, item_id, item_title, item_kind
        )

    def notify_lost_found_resolved(
        self, recipient_id: UUID, actor: User, item_id: UUID, item_title: str, item_kind: str
    ) -> None:
        self._notify_lost_found(
            recipient_id,
            actor,
            NotificationType.LOST_FOUND_RESOLVED,
            item_id,
            item_title,
            item_kind,
        )

    def notify_lost_found_closed(
        self, actor: User, owner_id: UUID, item_id: UUID, item_title: str, item_kind: str
    ) -> None:
        informed = set(
            self._notifications.list_recipient_ids_for_entity(
                item_id, [NotificationType.LOST_FOUND_NEARBY]
            )
        )
        responders = set(
            self._notifications.list_actor_ids_for_entity(item_id, LOST_FOUND_RESPONSE_TYPES)
        )
        for recipient_id in (informed | responders) - {actor.id, owner_id}:
            self._notify_lost_found(
                recipient_id,
                actor,
                NotificationType.LOST_FOUND_CLOSED,
                item_id,
                item_title,
                item_kind,
            )

    def has_lost_found_response(self, recipient_id: UUID, actor: User, item_id: UUID) -> bool:
        return self._notifications.exists_from_actor(
            recipient_id, actor.id, item_id, LOST_FOUND_RESPONSE_TYPES
        )

    def notify_lost_found_response(
        self,
        recipient_id: UUID,
        actor: User,
        item_id: UUID,
        item_title: str,
        item_kind: str,
        note: str | None,
    ) -> None:
        type_ = (
            NotificationType.LOST_FOUND_FOUND
            if item_kind == LOST_ITEM_KIND
            else NotificationType.LOST_FOUND_CLAIMED
        )
        metadata = {ITEM_TITLE_METADATA_KEY: item_title, ITEM_KIND_METADATA_KEY: item_kind}
        if note:
            metadata[RESPONSE_NOTE_METADATA_KEY] = note
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=type_,
            entity_type=LOST_FOUND_ENTITY_TYPE,
            entity_id=item_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata=metadata,
        )

    def _notify_lost_found(
        self,
        recipient_id: UUID,
        actor: User,
        type_: NotificationType,
        item_id: UUID,
        item_title: str,
        item_kind: str,
    ) -> None:
        self._create_if_enabled(
            recipient_id=recipient_id,
            actor_id=actor.id,
            type_=type_,
            entity_type=LOST_FOUND_ENTITY_TYPE,
            entity_id=item_id,
            is_enabled=lambda settings: settings.system_updates,
            metadata={ITEM_TITLE_METADATA_KEY: item_title, ITEM_KIND_METADATA_KEY: item_kind},
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
        was_unread = not notification.is_read
        updated = self._notifications.mark_read(notification)
        if was_unread:
            self._publish_read(recipient.id, {"notification_id": str(updated.id), "is_read": True})
        return self._to_read(updated)

    def mark_all_notifications_read(self, recipient: User) -> None:
        marked_count = self._notifications.mark_all_read(recipient.id)
        if marked_count:
            self._publish_read(recipient.id, {"all_read": True})

    def _get_owned(self, notification_id: UUID, recipient_id: UUID) -> Notification:
        notification = self._notifications.get_by_id_for_recipient(notification_id, recipient_id)
        if notification is None:
            raise NotFoundError(NotificationMessages.NOT_FOUND)
        return notification

    def _create_if_enabled(
        self,
        *,
        recipient_id: UUID,
        actor_id: UUID | None,
        type_: NotificationType,
        entity_type: str,
        entity_id: UUID,
        is_enabled: Callable[[UserNotificationSettings], bool],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if actor_id is not None and recipient_id == actor_id:
            return
        settings = self._get_or_create_settings(recipient_id)
        if not is_enabled(settings):
            return
        notification = self._notifications.add(
            Notification(
                recipient_id=recipient_id,
                actor_id=actor_id,
                type=type_,
                entity_type=entity_type,
                entity_id=entity_id,
                metadata_=metadata,
            )
        )
        self._publish_created(notification)
        if settings.push_enabled:
            self._push_created(notification)

    def _push_created(self, notification: Notification) -> None:
        if not self._push.enabled:
            return
        try:
            read = self._to_read(notification)
            self._push.publish(
                PushMessage(
                    user_id=notification.recipient_id,
                    title=NotificationMessages.PUSH_TITLE,
                    body=read.message,
                    data={
                        PUSH_NOTIFICATION_ID_KEY: str(read.id),
                        PUSH_TYPE_KEY: read.type.value,
                        PUSH_ENTITY_TYPE_KEY: read.entity_type or "",
                        PUSH_ENTITY_ID_KEY: str(read.entity_id) if read.entity_id else "",
                    },
                )
            )
        except Exception:
            logger.exception("Failed to queue push for user %s", notification.recipient_id)

    def _publish_created(self, notification: Notification) -> None:
        self._publish_if_connected(
            notification.recipient_id,
            lambda: RealtimeEvent(
                type=RealtimeEventType.NOTIFICATION_CREATED,
                data={
                    "notification": self._to_read(notification).model_dump(mode="json"),
                    "unread_count": self._notifications.count_unread(notification.recipient_id),
                },
            ),
        )

    def _publish_read(self, recipient_id: UUID, change: dict[str, Any]) -> None:
        self._publish_if_connected(
            recipient_id,
            lambda: RealtimeEvent(
                type=RealtimeEventType.NOTIFICATION_READ,
                data={**change, "unread_count": self._notifications.count_unread(recipient_id)},
            ),
        )

    def _publish_if_connected(
        self, recipient_id: UUID, build_event: Callable[[], RealtimeEvent]
    ) -> None:
        try:
            if self._publisher.has_connections(recipient_id):
                self._publisher.publish_to_user(recipient_id, build_event())
        except Exception:
            logger.exception("Failed to publish realtime event to user %s", recipient_id)

    def _get_or_create_settings(self, user_id: UUID) -> UserNotificationSettings:
        settings = self._settings.get_by_user_id(user_id)
        if settings is not None:
            return settings
        return self._settings.add(UserNotificationSettings(user_id=user_id))

    def _to_read(self, notification: Notification) -> NotificationRead:
        return NotificationRead(
            id=notification.id,
            type=notification.type,
            message=self._render_message(notification),
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            is_read=notification.is_read,
            created_at=notification.created_at,
        )

    def _render_message(self, notification: Notification) -> str:
        metadata = notification.metadata_ or {}
        message = NOTIFICATION_MESSAGE_TEMPLATES[notification.type].format(
            actor=self._actor_name(notification.actor_id),
            role_name=metadata.get(ROLE_NAME_METADATA_KEY, ""),
            category_name=metadata.get(CATEGORY_NAME_METADATA_KEY, ""),
            community_name=metadata.get(COMMUNITY_NAME_METADATA_KEY, ""),
            review_note=metadata.get(REVIEW_NOTE_METADATA_KEY, ""),
            business_name=metadata.get(BUSINESS_NAME_METADATA_KEY, ""),
            deal_name=metadata.get(DEAL_NAME_METADATA_KEY, ""),
            order_number=metadata.get(ORDER_NUMBER_METADATA_KEY, ""),
            item_title=metadata.get(ITEM_TITLE_METADATA_KEY, ""),
            item_kind=metadata.get(ITEM_KIND_METADATA_KEY, ""),
        )
        note = metadata.get(RESPONSE_NOTE_METADATA_KEY)
        if note:
            message += NotificationMessages.RESPONSE_NOTE_SUFFIX.format(response_note=note)
        return message

    def _actor_name(self, actor_id: UUID | None) -> str:
        if actor_id is None:
            return NotificationMessages.UNKNOWN_ACTOR
        actor = self._users.get_by_id_including_deleted(actor_id)
        if actor is None:
            return NotificationMessages.UNKNOWN_ACTOR
        return f"{actor.first_name} {actor.last_name}"
