from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import NotFoundError
from app.core.messages import CommunityMessages
from app.models.user import User
from app.repositories.community_repository import CommunityRepository
from app.repositories.post_repository import PostRepository
from app.services.activity_log_service import ActivityLogService
from app.services.community_access import ensure_owner
from app.services.notification_service import NotificationService


class CommunityPostModerationService:
    def __init__(self, db: Session) -> None:
        self._communities = CommunityRepository(db)
        self._posts = PostRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def remove_post(self, community_id: UUID, post_id: UUID, actor: User, reason: str) -> None:
        community = self._communities.get_by_id(community_id)
        if community is None:
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        ensure_owner(community, actor)
        post = self._posts.get_in_community(community.id, post_id)
        if post is None:
            raise NotFoundError(CommunityMessages.POST_NOT_FOUND)
        self._posts.soft_remove(post, actor.id, reason)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COMMUNITY_POST_REMOVED,
            entity_type="post",
            entity_id=post.id,
            metadata={"community_id": str(community.id)},
        )
        self._notifications.notify_community_post_removed(
            post.user_id, actor, community.id, community.name, reason
        )
