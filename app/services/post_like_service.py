from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import NotFoundError
from app.core.messages import PostReactionMessages
from app.models.post import Post
from app.models.post_like import PostLike, ReactionType
from app.models.user import User
from app.repositories.post_like_repository import PostLikeRepository
from app.services.activity_log_service import ActivityLogService
from app.services.notification_service import NotificationService
from app.services.post_service import PostService


class PostLikeService:
    def __init__(self, db: Session) -> None:
        self._likes = PostLikeRepository(db)
        self._posts = PostService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)

    def react(self, post_id: UUID, reaction_type: ReactionType, actor: User) -> PostLike:
        post = self._posts.get_visible(post_id, actor)
        existing = self._likes.get_by_post_and_user(post.id, actor.id)
        if existing is None:
            return self._add_reaction(post, reaction_type, actor)
        if existing.reaction_type == reaction_type:
            return existing
        return self._change_reaction(post, existing, reaction_type, actor)

    def _add_reaction(self, post: Post, reaction_type: ReactionType, actor: User) -> PostLike:
        reaction = self._likes.add(
            PostLike(post_id=post.id, user_id=actor.id, reaction_type=reaction_type)
        )
        self._posts.increment_likes_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_REACTED,
            entity_type="post",
            entity_id=post.id,
            metadata={"reaction_type": reaction_type.value},
        )
        self._notifications.notify_post_liked(post=post, actor=actor)
        return reaction

    def _change_reaction(
        self, post: Post, reaction: PostLike, reaction_type: ReactionType, actor: User
    ) -> PostLike:
        reaction.reaction_type = reaction_type
        saved = self._likes.save(reaction)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_REACTION_CHANGED,
            entity_type="post",
            entity_id=post.id,
            metadata={"reaction_type": reaction_type.value},
        )
        return saved

    def remove_reaction(self, post_id: UUID, actor: User) -> None:
        post = self._posts.get(post_id)
        reaction = self._likes.get_by_post_and_user(post.id, actor.id)
        if reaction is None:
            raise NotFoundError(PostReactionMessages.NOT_FOUND)
        self._likes.delete(reaction)
        self._posts.decrement_likes_count(post.id)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_REACTION_REMOVED,
            entity_type="post",
            entity_id=post.id,
        )
