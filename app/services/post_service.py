import logging
import uuid
from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import CommunityMessages, PostMessages
from app.core.permissions import PermissionName
from app.core.timezone import app_now
from app.models.post import Post, PostAudience, PostStatus, PostVisibility
from app.models.post_media import PostMedia
from app.models.tag import Tag
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.community_member_repository import CommunityMemberRepository
from app.repositories.community_repository import CommunityRepository
from app.repositories.post_like_repository import PostLikeRepository
from app.repositories.post_media_repository import PostMediaRepository
from app.repositories.post_repository import PostRepository, PostVisibilityScope
from app.repositories.saved_post_repository import SavedPostRepository
from app.repositories.tag_repository import TagRepository
from app.repositories.user_repository import UserRepository
from app.schemas.pagination import PaginationParams
from app.schemas.post import PostCommunityRead, PostCreate, PostDetailRead, PostUpdate
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.geography_service import GeographyService
from app.services.user_native_place_service import NearbyArea, UserNativePlaceService
from app.utils.slug import build_unique_slug, slugify

logger = logging.getLogger("app.post")

METERS_PER_KM = 1000
DISTANCE_KM_DECIMALS = 2


def _build_location(latitude: float | None, longitude: float | None) -> Any | None:
    if latitude is None or longitude is None:
        return None
    return func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326)


class PostService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._posts = PostRepository(db)
        self._users = UserRepository(db)
        self._communities = CommunityRepository(db)
        self._community_members = CommunityMemberRepository(db)
        self._media = PostMediaRepository(db)
        self._tags = TagRepository(db)
        self._saved_posts = SavedPostRepository(db)
        self._reactions = PostLikeRepository(db)
        self._geography = GeographyService(db)
        self._native_places = UserNativePlaceService(db)
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
        return self._geography.format_location_name(taluk)

    def _ensure_not_duplicate(
        self,
        user_id: UUID,
        title: str | None,
        content: str | None,
        exclude_post_id: UUID | None = None,
    ) -> None:
        if title is not None:
            is_duplicate = self._posts.exists_with_title(user_id, title, exclude_post_id)
        elif content is not None:
            is_duplicate = self._posts.exists_with_content(user_id, content, exclude_post_id)
        else:
            is_duplicate = False
        if is_duplicate:
            raise BusinessRuleError(PostMessages.DUPLICATE_CONTENT)

    def create(
        self,
        payload: PostCreate,
        acting_user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Post:
        if payload.community_id is not None:
            self._ensure_can_post_in_community(payload.community_id, acting_user)
        return self._create(payload, acting_user, ip_address, user_agent)

    def create_as_admin(
        self,
        payload: PostCreate,
        acting_user: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Post:
        if payload.community_id is not None:
            self._ensure_community_published(payload.community_id)
        return self._create(payload, acting_user, ip_address, user_agent)

    def _create(
        self,
        payload: PostCreate,
        acting_user: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> Post:
        self._ensure_not_duplicate(acting_user.id, payload.title, payload.content)
        post_id = uuid.uuid4()
        post = Post(
            id=post_id,
            user_id=acting_user.id,
            community_id=payload.community_id,
            slug=build_unique_slug(payload.title, post_id),
            title=payload.title,
            content=payload.content,
            status=payload.status,
            audience=payload.audience,
            visibility=payload.visibility or self._default_visibility(payload.community_id),
            scheduled_at=payload.scheduled_at,
            published_at=app_now() if payload.status == PostStatus.PUBLISHED else None,
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
            metadata={
                "status": post.status.value,
                "audience": post.audience.value,
                "visibility": post.visibility.value,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return post

    @staticmethod
    def _default_visibility(community_id: UUID | None) -> PostVisibility:
        return PostVisibility.PUBLIC if community_id is None else PostVisibility.PRIVATE

    def _ensure_community_published(self, community_id: UUID) -> None:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)

    def _ensure_can_post_in_community(self, community_id: UUID, actor: User) -> None:
        self._ensure_community_published(community_id)
        if not self._community_members.is_active_member(community_id, actor.id):
            raise AuthorizationError(CommunityMessages.POSTING_NOT_ALLOWED)

    def get(self, post_id: UUID) -> Post:
        post = self._posts.get_by_id(post_id)
        if post is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        return post

    def _visibility_scope(
        self, viewer: User | None, include_member_communities: bool = False
    ) -> PostVisibilityScope:
        if viewer is None:
            return PostVisibilityScope()
        if has_permission(viewer, PermissionName.POST_UPDATE_ANY):
            return PostVisibilityScope(include_unpublished=True)
        return PostVisibilityScope(
            owner_id=viewer.id,
            viewer_is_adult=viewer.is_adult is True,
            member_id=viewer.id if include_member_communities else None,
        )

    def get_visible(self, post_id: UUID, viewer: User | None) -> Post:
        post = self._posts.get_visible_by_id(post_id, self._visibility_scope(viewer, True))
        if post is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        return post

    def get_visible_by_slug(self, slug: str, viewer: User | None) -> Post:
        post = self._posts.get_visible_by_slug(slug, self._visibility_scope(viewer, True))
        if post is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        return post

    def get_detail(self, post_id: UUID, viewer: User | None) -> PostDetailRead:
        return self._to_detail(self.get_visible(post_id, viewer), viewer)

    def get_detail_by_slug(self, slug: str, viewer: User | None) -> PostDetailRead:
        return self._to_detail(self.get_visible_by_slug(slug, viewer), viewer)

    def _to_detail(self, post: Post, viewer: User | None) -> PostDetailRead:
        author = self._users.get_by_id_including_deleted(post.user_id)
        if author is None:
            raise NotFoundError(PostMessages.NOT_FOUND)
        media = self._media.list_by_post(post.id)
        tags = self._tags.list_by_post(post.id)
        is_saved = viewer is not None and self._saved_posts.exists(viewer.id, post.id)
        reaction_counts = self._reactions.count_by_type([post.id]).get(post.id, {})
        my_reaction = (
            self._reactions.list_user_reactions(viewer.id, [post.id]).get(post.id)
            if viewer is not None
            else None
        )
        community = self._post_communities([post], viewer).get(post.id)
        return PostDetailRead.from_post(
            post, author, media, tags, is_saved, reaction_counts, my_reaction, community
        )

    def _post_communities(
        self, posts: list[Post], viewer: User | None
    ) -> dict[UUID, PostCommunityRead]:
        community_ids = list({post.community_id for post in posts if post.community_id is not None})
        if not community_ids:
            return {}
        memberships = (
            self._community_members.status_by_community(viewer.id, community_ids) if viewer else {}
        )
        reads = {
            community.id: PostCommunityRead(
                id=community.id,
                name=community.name,
                image_url=community.image_url,
                my_membership=memberships.get(community.id),
            )
            for community in self._communities.list_by_ids(community_ids)
        }
        return {
            post.id: reads[post.community_id]
            for post in posts
            if post.community_id is not None and post.community_id in reads
        }

    def list_tags(self, post_id: UUID) -> list[Tag]:
        return self._tags.list_by_post(post_id)

    def list_visible_tags(self, post_id: UUID, viewer: User | None) -> list[Tag]:
        return self.list_tags(self.get_visible(post_id, viewer).id)

    def _to_details(
        self, posts: list[Post], total: int, viewer: User | None
    ) -> tuple[list[PostDetailRead], int]:
        if not posts:
            return [], total
        author_ids = list({post.user_id for post in posts})
        authors = {user.id: user for user in self._users.get_by_ids_including_deleted(author_ids)}
        post_ids = [post.id for post in posts]
        media_by_post: dict[UUID, list[PostMedia]] = defaultdict(list)
        for media_item in self._media.list_by_posts(post_ids):
            media_by_post[media_item.post_id].append(media_item)
        tags_by_post: dict[UUID, list[Tag]] = self._tags.list_by_posts(post_ids)
        saved_post_ids = (
            self._saved_posts.list_saved_post_ids(viewer.id, post_ids) if viewer else set()
        )
        reaction_counts = self._reactions.count_by_type(post_ids)
        my_reactions = self._reactions.list_user_reactions(viewer.id, post_ids) if viewer else {}
        communities = self._post_communities(posts, viewer)
        items = [
            PostDetailRead.from_post(
                post,
                authors[post.user_id],
                media_by_post[post.id],
                tags_by_post[post.id],
                post.id in saved_post_ids,
                reaction_counts.get(post.id),
                my_reactions.get(post.id),
                communities.get(post.id),
            )
            for post in posts
        ]
        return items, total

    def default_feed_area(self, viewer: User | None) -> NearbyArea | None:
        if viewer is None:
            return None
        return self._native_places.default_nearby_area(viewer)

    def list_for_admin_with_details(
        self,
        params: PaginationParams,
        viewer: User,
        status: PostStatus | None = None,
        audience: PostAudience | None = None,
        visibility: PostVisibility | None = None,
        user_id: UUID | None = None,
        community_id: UUID | None = None,
        query: str | None = None,
    ) -> tuple[list[PostDetailRead], int]:
        posts, total = self._posts.list_for_admin(
            params, status, audience, visibility, user_id, community_id, query
        )
        return self._to_details(posts, total, viewer)

    def get_detail_for_admin(self, post_id: UUID, viewer: User) -> PostDetailRead:
        return self._to_detail(self.get(post_id), viewer)

    def list_with_details(
        self, params: PaginationParams, viewer: User | None, user_id: UUID | None = None
    ) -> tuple[list[PostDetailRead], int]:
        posts, total = self._posts.list(params, self._visibility_scope(viewer), user_id)
        return self._to_details(posts, total, viewer)

    def list_nearby_with_details(
        self,
        params: PaginationParams,
        viewer: User | None,
        latitude: float,
        longitude: float,
        radius_km: float | None,
        query: str | None = None,
        user_id: UUID | None = None,
        priority_radius_km: float | None = None,
    ) -> tuple[list[tuple[PostDetailRead, float]], int]:
        radius_meters = radius_km * METERS_PER_KM if radius_km is not None else None
        priority_radius_meters = (
            priority_radius_km * METERS_PER_KM if priority_radius_km is not None else None
        )
        rows, total = self._posts.list_nearby(
            params,
            self._visibility_scope(viewer),
            latitude,
            longitude,
            radius_meters,
            query,
            user_id,
            priority_radius_meters,
        )
        details, _ = self._to_details([post for post, _ in rows], total, viewer)
        distances_km = [round(meters / METERS_PER_KM, DISTANCE_KM_DECIMALS) for _, meters in rows]
        return list(zip(details, distances_km, strict=True)), total

    def list_by_user_with_details(
        self,
        user_id: UUID,
        params: PaginationParams,
        viewer: User | None,
        order_by_likes: bool = False,
    ) -> tuple[list[PostDetailRead], int]:
        scope = self._visibility_scope(viewer)
        posts, total = self._posts.list_by_user(user_id, params, scope, order_by_likes)
        return self._to_details(posts, total, viewer)

    def search_with_details(
        self,
        params: PaginationParams,
        viewer: User | None,
        tag_names: list[str] | None = None,
        query: str | None = None,
        order_by_likes: bool = False,
        location: str | None = None,
        match_any_term: bool = False,
    ) -> tuple[list[PostDetailRead], int]:
        tag_slugs = [slugify(name) for name in tag_names] if tag_names else None
        scope = self._visibility_scope(viewer)
        posts, total = self._posts.search(
            params, scope, tag_slugs, query, order_by_likes, location, match_any_term
        )
        return self._to_details(posts, total, viewer)

    def search_nearby_with_details(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        limit: int,
        viewer: User | None,
    ) -> list[tuple[PostDetailRead, float]]:
        posts_with_distance = self._posts.search_nearby(
            latitude, longitude, radius_meters, self._visibility_scope(viewer), limit
        )
        posts = [post for post, _ in posts_with_distance]
        details, _ = self._to_details(posts, len(posts), viewer)
        distances = [distance for _, distance in posts_with_distance]
        return list(zip(details, distances, strict=True))

    def list_saved_with_details(
        self, user_id: UUID, params: PaginationParams, viewer: User
    ) -> tuple[list[PostDetailRead], int]:
        scope = self._visibility_scope(viewer, True)
        posts, total = self._posts.list_saved_by_user(user_id, params, scope)
        return self._to_details(posts, total, viewer)

    def list_by_collection_with_details(
        self, collection_id: UUID, params: PaginationParams, viewer: User
    ) -> tuple[list[PostDetailRead], int]:
        scope = self._visibility_scope(viewer, True)
        posts, total = self._posts.list_by_collection(collection_id, params, scope)
        return self._to_details(posts, total, viewer)

    def details_by_ids(self, post_ids: list[UUID], viewer: User) -> dict[UUID, PostDetailRead]:
        if not post_ids:
            return {}
        posts = self._posts.list_by_ids(post_ids)
        details, _ = self._to_details(posts, len(posts), viewer)
        return {detail.id: detail for detail in details}

    def announce_community_post(self, post: Post, newly_published: bool) -> None:
        if post.community_id is None or post.status != PostStatus.PUBLISHED or not newly_published:
            return
        try:
            event_data = {
                "community_id": str(post.community_id),
                "post_id": str(post.id),
                "author_id": str(post.user_id),
            }
            for user_id in self._community_members.list_active_user_ids(post.community_id):
                if self._publisher.has_connections(user_id):
                    self._publisher.publish_to_user(
                        user_id,
                        RealtimeEvent(
                            type=RealtimeEventType.COMMUNITY_POST_CREATED, data=event_data
                        ),
                    )
        except Exception:
            logger.exception("Failed to announce community post %s", post.id)

    def list_community_posts_with_details(
        self,
        community_id: UUID,
        params: PaginationParams,
        viewer: User,
    ) -> tuple[list[PostDetailRead], int]:
        community = self._communities.get_by_id(community_id)
        if community is None or not self._communities.is_published(community):
            raise NotFoundError(CommunityMessages.NOT_FOUND)
        if not self._community_members.is_active_member(community_id, viewer.id):
            raise AuthorizationError(CommunityMessages.NOT_A_MEMBER)
        scope = self._visibility_scope(viewer, True)
        posts, total = self._posts.list_by_community(community_id, params, scope)
        return self._to_details(posts, total, viewer)

    def _ensure_still_in_community(self, post: Post, actor: User, override_permission: str) -> None:
        if (
            post.community_id is not None
            and not has_permission(actor, override_permission)
            and not self._community_members.is_active_member(post.community_id, actor.id)
        ):
            raise AuthorizationError(CommunityMessages.POSTING_NOT_ALLOWED)

    def update(self, post_id: UUID, payload: PostUpdate, actor: User) -> Post:
        post = self.get(post_id)
        self._ensure_still_in_community(post, actor, PermissionName.POST_CREATE_ANY)
        self.ensure_can_edit(post, actor)
        data: dict[str, Any] = payload.model_dump(
            exclude={"latitude", "longitude", "location_name", "tags"}, exclude_none=True
        )
        if data.get("visibility") == PostVisibility.PRIVATE and post.community_id is None:
            raise BusinessRuleError(PostMessages.PRIVATE_REQUIRES_COMMUNITY)
        new_status = data.get("status")
        if new_status == PostStatus.PUBLISHED and post.status != PostStatus.PUBLISHED:
            post.published_at = app_now()
            post.published_by = actor.id
        for field, value in data.items():
            setattr(post, field, value)
        if "title" in data or "content" in data:
            self._ensure_not_duplicate(post.user_id, post.title, post.content, post.id)
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
        self._ensure_still_in_community(post, actor, PermissionName.POST_DELETE_ANY)
        self.ensure_can_modify(post, actor, PermissionName.POST_DELETE_ANY)
        self._posts.soft_delete(post)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_DELETED,
            entity_type="post",
            entity_id=post.id,
        )

    def ensure_can_edit(self, post: Post, actor: User) -> None:
        if post.user_id != actor.id:
            raise AuthorizationError(PostMessages.NOT_OWNER)
        if post.status == PostStatus.BLOCKED:
            raise BusinessRuleError(PostMessages.BLOCKED_NOT_EDITABLE)

    def block(self, post_id: UUID, actor: User, reason: str | None = None) -> Post:
        post = self.get(post_id)
        if post.status == PostStatus.BLOCKED:
            raise BusinessRuleError(PostMessages.ALREADY_BLOCKED)
        if post.status != PostStatus.PUBLISHED:
            raise BusinessRuleError(PostMessages.ONLY_PUBLISHED_CAN_BE_BLOCKED)
        post.status = PostStatus.BLOCKED
        saved = self._posts.save(post)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_BLOCKED,
            entity_type="post",
            entity_id=post.id,
            metadata={"reason": reason} if reason else None,
        )
        return saved

    def unblock(self, post_id: UUID, actor: User) -> Post:
        post = self.get(post_id)
        if post.status != PostStatus.BLOCKED:
            raise BusinessRuleError(PostMessages.NOT_BLOCKED)
        post.status = PostStatus.PUBLISHED
        saved = self._posts.save(post)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.POST_UNBLOCKED,
            entity_type="post",
            entity_id=post.id,
        )
        return saved

    def ensure_can_modify(self, post: Post, actor: User, override_permission: str) -> None:
        if post.user_id != actor.id and not has_permission(actor, override_permission):
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

    def increment_saved_count(self, post_id: UUID) -> None:
        self._posts.increment_saved(post_id)

    def decrement_saved_count(self, post_id: UUID) -> None:
        self._posts.decrement_saved(post_id)
