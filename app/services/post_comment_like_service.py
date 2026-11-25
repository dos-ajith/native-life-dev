from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import NotFoundError
from app.core.messages import PostCommentLikeMessages, PostCommentMessages
from app.models.post_comment import PostComment
from app.models.post_comment_like import PostCommentLike
from app.models.user import User
from app.repositories.post_comment_like_repository import PostCommentLikeRepository
from app.repositories.post_comment_repository import PostCommentRepository
from app.services.activity_log_service import ActivityLogService
from app.services.notification_service import NotificationService
from app.services.post_service import PostService


class PostCommentLikeService:
    def __init__(self, db: Session) -> None:
        self._likes = PostCommentLikeRepository(db)
        self._comments = PostCommentRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def like(self, comment_id: UUID, actor: User) -> None:
        comment = self._get_comment(comment_id)
        self._posts.get_visible(comment.post_id, actor)
        if self._likes.get_by_comment_and_user(comment.id, actor.id) is not None:
            return
        self._likes.add(PostCommentLike(comment_id=comment.id, user_id=actor.id))
        self._comments.increment_likes(comment.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COMMENT_LIKED,
            entity_type="post_comment",
            entity_id=comment.id,
            metadata={"post_id": str(comment.post_id)},
        )
        self._notifications.notify_comment_liked(comment=comment, actor=actor)

    def unlike(self, comment_id: UUID, actor: User) -> None:
        comment = self._get_comment(comment_id)
        like = self._likes.get_by_comment_and_user(comment.id, actor.id)
        if like is None:
            raise NotFoundError(PostCommentLikeMessages.NOT_FOUND)
        self._likes.delete(like)
        self._comments.decrement_likes(comment.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COMMENT_UNLIKED,
            entity_type="post_comment",
            entity_id=comment.id,
            metadata={"post_id": str(comment.post_id)},
        )

    def _get_comment(self, comment_id: UUID) -> PostComment:
        comment = self._comments.get_by_id(comment_id)
        if comment is None:
            raise NotFoundError(PostCommentMessages.NOT_FOUND)
        return comment
