from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PostLikeMessages
from app.models.post_like import PostLike
from app.models.user import User
from app.repositories.post_like_repository import PostLikeRepository
from app.services.activity_log_service import ActivityLogService
from app.services.post_service import PostService


class PostLikeService:
    def __init__(self, db: Session) -> None:
        self._likes = PostLikeRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def like(self, post_id: UUID, actor: User) -> PostLike:
        post = self._posts.get(post_id)
        if self._likes.get_by_post_and_user(post.id, actor.id) is not None:
            raise BusinessRuleError(PostLikeMessages.ALREADY_LIKED)
        like = self._likes.add(PostLike(post_id=post.id, user_id=actor.id))
        self._posts.increment_likes_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_LIKED,
            entity_type="post",
            entity_id=post.id,
        )
        return like

    def unlike(self, post_id: UUID, actor: User) -> None:
        post = self._posts.get(post_id)
        like = self._likes.get_by_post_and_user(post.id, actor.id)
        if like is None:
            raise NotFoundError(PostLikeMessages.NOT_FOUND)
        self._likes.delete(like)
        self._posts.decrement_likes_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_UNLIKED,
            entity_type="post",
            entity_id=post.id,
        )
