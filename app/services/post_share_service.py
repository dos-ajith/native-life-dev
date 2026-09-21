from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.post_share import PostShare
from app.models.user import User
from app.repositories.post_share_repository import PostShareRepository
from app.services.activity_log_service import ActivityLogService
from app.services.post_service import PostService


class PostShareService:
    def __init__(self, db: Session) -> None:
        self._shares = PostShareRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def share(self, post_id: UUID, actor: User, utm_source: str | None = None) -> PostShare:
        post = self._posts.get(post_id)
        share = self._shares.add(
            PostShare(post_id=post.id, user_id=actor.id, utm_source=utm_source)
        )
        self._posts.increment_shares_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_SHARED,
            entity_type="post",
            entity_id=post.id,
            metadata={"utm_source": utm_source} if utm_source is not None else None,
        )
        return share
