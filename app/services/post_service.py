from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import PostMessages
from app.models.post import Post, PostStatus
from app.models.post_media import PostMedia
from app.models.tag import Tag
from app.models.user import User, UserType
from app.repositories.post_media_repository import PostMediaRepository
from app.repositories.post_repository import PostRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.post import PostCreate, PostDetailRead, PostUpdate
from app.services.activity_log_service import ActivityLogService
from app.services.geography_service import GeographyService


def _build_location(latitude: float | None, longitude: float | None) -> Any | None:
    if latitude is None or longitude is None:
        return None
    return func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326)


class PostService:
    def __init__(self, db: Session) -> None:
        self._posts = PostRepository(db)
        self._users = UserRepository(db)
        self._media = PostMediaRepository(db)
        self._tags = TagRepository(db)
        self._geography = GeographyService(db)
        self._activity_logs = ActivityLogService(db)

    def _resolve_location_name(
        self, location_name: str | None, latitude: float | None, longitude: float | None
    ) -> str | None:
        if location_name is not None:
            return location_name
        if latitude is None or longitude is None:
            return None
        try:
            taluk = self._geography.reverse_geocode(latitude, longitude)
        except NotFoundError:
            return None
        return f"{taluk.name}, {taluk.district.name}, {taluk.district.state.name}"

    def create(
        self,
        payload: PostCreate,
        acting_user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Post:
        post = Post(
            user_id=acting_user.id,
            title=payload.title,
            content=payload.content,
            status=payload.status,
            scheduled_at=payload.scheduled_at,
            published_at=datetime.now(UTC) if payload.status == PostStatus.PUBLISHED else None,
            published_by=acting_user.id if payload.status == PostStatus.PUBLISHED else None,
            location=_build_location(payload.latitude, payload.longitude),
            location_name=self._resolve_location_name(
                payload.location_name, payload.latitude, payload.longitude
            ),
        )
        post = self._posts.add(post)
        self._activity_logs.log(
            actor=acting_user,
            action=ActivityAction.POST_CREATED,
            entity_type="post",
            entity_id=post.id,
            metadata={"status": post.status.value},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return post

    def get(self, post_id: UUID) -> Post:
        post = self._posts.get_by_id(post_id)
        if post is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        return post

    def get_detail(self, post_id: UUID) -> PostDetailRead:
        post = self.get(post_id)
        author = self._users.get_by_id_including_deleted(post.user_id)
        if author is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        media = self._media.list_by_post(post.id)
        tags = self._tags.list_by_post(post.id)
        return PostDetailRead.from_post(post, author, media, tags)

    def list_tags(self, post_id: UUID) -> list[Tag]:
        return self._tags.list_by_post(post_id)

    def list_with_details(self, params: PaginationParams) -> tuple[list[PostDetailRead], int]:
        posts, total = self._posts.list(params)
        if not posts:
            return [], total
        author_ids = list({post.user_id for post in posts})
        authors = {
            user.id: user for user in self._users.get_by_ids_including_deleted(author_ids)
        }
        post_ids = [post.id for post in posts]
        media_by_post: dict[UUID, list[PostMedia]] = defaultdict(list)
        for media_item in self._media.list_by_posts(post_ids):
            media_by_post[media_item.post_id].append(media_item)
        tags_by_post: dict[UUID, list[Tag]] = self._tags.list_by_posts(post_ids)
        items = [
            PostDetailRead.from_post(
                post, authors[post.user_id], media_by_post[post.id], tags_by_post[post.id]
            )
            for post in posts
        ]
        return items, total

    def list(self, params: PaginationParams) -> tuple[list[Post], int]:
        return self._posts.list(params)

    def update(self, post_id: UUID, payload: PostUpdate, actor: User) -> Post:
        post = self.get(post_id)
        self.ensure_can_modify(post, actor)
        data: dict[str, Any] = payload.model_dump(
            exclude={"latitude", "longitude", "location_name", "tags"}, exclude_none=True
        )
        new_status = data.get("status")
        if new_status == PostStatus.PUBLISHED and post.status != PostStatus.PUBLISHED:
            post.published_at = datetime.now(UTC)
            post.published_by = actor.id
        for field, value in data.items():
            setattr(post, field, value)
        if payload.latitude is not None and payload.longitude is not None:
            post.location = _build_location(payload.latitude, payload.longitude)
            post.location_name = self._resolve_location_name(
                payload.location_name, payload.latitude, payload.longitude
            )
        elif payload.location_name is not None:
            post.location_name = payload.location_name
        saved = self._posts.save(post)
        updated_fields = list(data.keys())
        if payload.tags is not None:
            updated_fields.append("tags")
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_UPDATED,
            entity_type="post",
            entity_id=post.id,
            metadata={"updated_fields": updated_fields},
        )
        return saved

    def delete(self, post_id: UUID, actor: User) -> None:
        post = self.get(post_id)
        self.ensure_can_modify(post, actor)
        self._posts.soft_delete(post)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_DELETED,
            entity_type="post",
            entity_id=post.id,
        )

    def ensure_can_modify(self, post: Post, actor: User) -> None:
        if post.user_id != actor.id and actor.user_type != UserType.PRIVATE:
            raise AuthorizationError(PostMessages.NOT_OWNER)

    def increment_likes_count(self, post_id: UUID) -> None:
        self._posts.increment_likes(post_id)

    def decrement_likes_count(self, post_id: UUID) -> None:
        self._posts.decrement_likes(post_id)

    def increment_comments_count(self, post_id: UUID) -> None:
        self._posts.increment_comments(post_id)

    def decrement_comments_count(self, post_id: UUID) -> None:
        self._posts.decrement_comments(post_id)

    def increment_shares_count(self, post_id: UUID) -> None:
        self._posts.increment_shares(post_id)
