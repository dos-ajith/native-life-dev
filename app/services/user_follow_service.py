from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import UserFollowMessages
from app.models.user import User
from app.repositories.user_follow_repository import UserFollowRepository
from app.schemas.pagination import PaginationParams
from app.schemas.user_follow import FollowCountsRead
from app.services.activity_log_service import ActivityLogService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService


class UserFollowService:
    def __init__(self, db: Session) -> None:
        self._follows = UserFollowRepository(db)
        self._users = UserService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def follow(self, target_id: UUID, actor: User) -> None:
        if target_id == actor.id:
            raise BusinessRuleError(UserFollowMessages.CANNOT_FOLLOW_SELF)
        target = self._users.get(target_id)
        if not self._follows.create(actor.id, target.id):
            raise BusinessRuleError(UserFollowMessages.ALREADY_FOLLOWING)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_FOLLOWED,
            entity_type="user",
            entity_id=target.id,
        )
        self._notifications.notify_user_followed(follower=actor, followed_id=target.id)

    def unfollow(self, target_id: UUID, actor: User) -> None:
        if target_id == actor.id:
            raise BusinessRuleError(UserFollowMessages.CANNOT_UNFOLLOW_SELF)
        if not self._follows.delete(actor.id, target_id):
            raise NotFoundError(UserFollowMessages.NOT_FOLLOWING)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.USER_UNFOLLOWED,
            entity_type="user",
            entity_id=target_id,
        )

    def is_following(self, follower_id: UUID, following_id: UUID) -> bool:
        return self._follows.exists(follower_id, following_id)

    def status(self, target_id: UUID, actor: User) -> bool:
        target = self._users.get(target_id)
        return self.is_following(actor.id, target.id)

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
