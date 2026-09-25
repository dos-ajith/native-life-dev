from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import UserFollowMessages
from app.models.user import User
from app.models.user_settings_enums import ProfileVisibility
from app.repositories.user_follow_repository import UserFollowRepository
from app.repositories.user_follow_request_repository import UserFollowRequestRepository
from app.repositories.user_privacy_settings_repository import UserPrivacySettingsRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user_follow import FollowCountsRead, FollowStatusRead
from app.services.activity_log_service import ActivityLogService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService


class UserFollowService:
    def __init__(self, db: Session) -> None:
        self._follows = UserFollowRepository(db)
        self._requests = UserFollowRequestRepository(db)
        self._privacy = UserPrivacySettingsRepository(db)
        self._users = UserService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def follow(self, target_id: UUID, actor: User) -> FollowStatusRead:
        if target_id == actor.id:
            raise BusinessRuleError(UserFollowMessages.CANNOT_FOLLOW_SELF)
        target = self._users.get(target_id)
        if self._follows.exists(actor.id, target.id):
            raise BusinessRuleError(UserFollowMessages.ALREADY_FOLLOWING)
        if self._is_private(target.id):
            self._request(target, actor)
            return FollowStatusRead(is_following=False, is_requested=True)
        self._follow_immediately(target, actor)
        return FollowStatusRead(is_following=True, is_requested=False)

    def unfollow(self, target_id: UUID, actor: User) -> bool:
        if target_id == actor.id:
            raise BusinessRuleError(UserFollowMessages.CANNOT_UNFOLLOW_SELF)
        if self._follows.delete(actor.id, target_id):
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.USER_UNFOLLOWED,
                entity_type="user",
                entity_id=target_id,
            )
            return False
        if self._requests.delete(actor.id, target_id):
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.USER_FOLLOW_REQUEST_CANCELLED,
                entity_type="user",
                entity_id=target_id,
            )
            return True
        raise NotFoundError(UserFollowMessages.NOT_FOLLOWING_OR_REQUESTED)

    def accept(self, requester_id: UUID, actor: User) -> None:
        if not self._requests.delete(requester_id, actor.id):
            raise NotFoundError(UserFollowMessages.REQUEST_NOT_FOUND)
        if not self._follows.create(requester_id, actor.id):
            raise BusinessRuleError(UserFollowMessages.ALREADY_FOLLOWING)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_FOLLOW_REQUEST_ACCEPTED,
            entity_type="user",
            entity_id=requester_id,
        )
        self._notifications.notify_follow_request_accepted(target=actor, requester_id=requester_id)

    def decline(self, requester_id: UUID, actor: User) -> None:
        if not self._requests.delete(requester_id, actor.id):
            raise NotFoundError(UserFollowMessages.REQUEST_NOT_FOUND)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_FOLLOW_REQUEST_DECLINED,
            entity_type="user",
            entity_id=requester_id,
        )

    def accept_all_pending(self, target: User) -> None:
        requester_ids = self._requests.delete_all_for_target(target.id)
        if not requester_ids:
            return
        accepted_ids = self._follows.bulk_create(target.id, requester_ids)
        for requester_id in accepted_ids:
            self._activity_logs.log(
                actor=target,
                action=ActivityAction.USER_FOLLOW_REQUEST_ACCEPTED,
                entity_type="user",
                entity_id=requester_id,
            )
            self._notifications.notify_follow_request_accepted(
                target=target, requester_id=requester_id
            )

    def status(self, target_id: UUID, actor: User) -> FollowStatusRead:
        target = self._users.get(target_id)
        if self._follows.exists(actor.id, target.id):
            return FollowStatusRead(is_following=True, is_requested=False)
        if self._requests.exists(actor.id, target.id):
            return FollowStatusRead(is_following=False, is_requested=True)
        return FollowStatusRead(is_following=False, is_requested=False)

    def counts(self, user_id: UUID) -> FollowCountsRead:
        user = self._users.get(user_id)
        return FollowCountsRead(
            followers_count=self._follows.count_followers(user.id),
            following_count=self._follows.count_following(user.id),
        )

    def list_followers(self, user_id: UUID, params: PaginationParams) -> tuple[list[User], int]:
        user = self._users.get(user_id)
        return (
            self._follows.list_followers(user.id, params),
            self._follows.count_followers(user.id),
        )

    def list_following(self, user_id: UUID, params: PaginationParams) -> tuple[list[User], int]:
        user = self._users.get(user_id)
        return (
            self._follows.list_following(user.id, params),
            self._follows.count_following(user.id),
        )

    def list_incoming_requests(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[User], int]:
        return (
            self._requests.list_incoming(actor.id, params),
            self._requests.count_incoming(actor.id),
        )

    def _is_private(self, target_id: UUID) -> bool:
        settings = self._privacy.get_by_user_id(target_id)
        if settings is None:
            return False
        return settings.profile_visibility == ProfileVisibility.PRIVATE

    def _follow_immediately(self, target: User, actor: User) -> None:
        if not self._follows.create(actor.id, target.id):
            raise BusinessRuleError(UserFollowMessages.ALREADY_FOLLOWING)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_FOLLOWED,
            entity_type="user",
            entity_id=target.id,
        )
        self._notifications.notify_user_followed(follower=actor, followed_id=target.id)

    def _request(self, target: User, actor: User) -> None:
        if not self._requests.create(actor.id, target.id):
            raise BusinessRuleError(UserFollowMessages.ALREADY_REQUESTED)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_FOLLOW_REQUESTED,
            entity_type="user",
            entity_id=target.id,
        )
        self._notifications.notify_follow_requested(requester=actor, target_id=target.id)
