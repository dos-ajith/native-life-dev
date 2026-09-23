from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import PostCommentMessages
from app.core.permissions import PermissionName
from app.models.post_comment import PostComment
from app.models.user import User
from app.repositories.post_comment_repository import PostCommentRepository
from app.schemas.pagination import PaginationParams
from app.schemas.post_comment import PostCommentCreate, PostCommentRead
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.post_service import PostService


class PostCommentService:
    def __init__(self, db: Session) -> None:
        self._comments = PostCommentRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def create(self, post_id: UUID, payload: PostCommentCreate, actor: User) -> PostComment:
        post = self._posts.get(post_id)
        if payload.parent_id is not None:
            parent = self._comments.get_by_id(payload.parent_id)
            if parent is None or parent.post_id != post.id:
                raise NotFoundError(PostCommentMessages.PARENT_NOT_FOUND)
        comment = PostComment(
            post_id=post.id,
            user_id=actor.id,
            parent_id=payload.parent_id,
            content=payload.content,
        )
        comment = self._comments.add(comment)
        self._posts.increment_comments_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COMMENT_CREATED,
            entity_type="post_comment",
            entity_id=comment.id,
            metadata={"post_id": str(post.id)},
        )
        return comment

    def list_for_post(
        self, post_id: UUID, params: PaginationParams, published_only: bool = False
    ) -> tuple[list[PostCommentRead], int]:
        self._posts.get_visible(post_id, published_only)
        roots, total = self._comments.list_roots_by_post(post_id, params)
        if not roots:
            return [], total
        all_comments = self._comments.list_all_by_post(post_id)
        return PostCommentRead.build_forest(roots, all_comments), total

    def delete(self, comment_id: UUID, actor: User) -> None:
        comment = self._get(comment_id)
        if comment.user_id != actor.id and not has_permission(
            actor, PermissionName.COMMENT_DELETE_ANY
        ):
            raise AuthorizationError(PostCommentMessages.NOT_OWNER)
        self._comments.soft_delete(comment)
        self._posts.decrement_comments_count(comment.post_id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.COMMENT_DELETED,
            entity_type="post_comment",
            entity_id=comment.id,
            metadata={"post_id": str(comment.post_id)},
        )

    def _get(self, comment_id: UUID) -> PostComment:
        comment = self._comments.get_by_id(comment_id)
        if comment is None:
            raise NotFoundError(PostCommentMessages.NOT_FOUND)
        return comment
