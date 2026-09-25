from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import SavedPostMessages
from app.models.user import User
from app.repositories.saved_post_repository import SavedPostRepository
from app.schemas.pagination import PaginationParams
from app.schemas.post import PostDetailRead
from app.services.activity_log_service import ActivityLogService
from app.services.post_service import PostService


class SavedPostService:
    def __init__(self, db: Session) -> None:
        self._saved_posts = SavedPostRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)

    def save(self, post_id: UUID, actor: User) -> None:
        post = self._posts.get_visible(post_id, actor)
        if not self._saved_posts.create(actor.id, post.id):
            raise BusinessRuleError(SavedPostMessages.ALREADY_SAVED)
        self._posts.increment_saved_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_SAVED,
            entity_type="post",
            entity_id=post.id,
        )

    def unsave(self, post_id: UUID, actor: User) -> None:
        post = self._posts.get(post_id)
        if not self._saved_posts.delete(actor.id, post.id):
            raise NotFoundError(SavedPostMessages.NOT_FOUND)
        self._posts.decrement_saved_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_UNSAVED,
            entity_type="post",
            entity_id=post.id,
        )

    def list_saved_posts(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[PostDetailRead], int]:
        return self._posts.list_saved_with_details(actor.id, params, actor)
