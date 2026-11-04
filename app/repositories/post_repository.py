import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import (
    ColumnElement,
    Select,
    case,
    cast,
    exists,
    func,
    literal,
    or_,
    select,
    true,
    update,
)
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.timezone import app_now
from app.models.collection_post import CollectionPost
from app.models.community import Community, CommunityStatus
from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.models.gis_village import GisVillage
from app.models.post import Post, PostAudience, PostStatus, PostVisibility
from app.models.post_tag import post_tags
from app.models.saved_post import SavedPost
from app.models.tag import Tag
from app.repositories.spatial import as_geography, point_from_coordinates
from app.schemas.community_timeline import TimelineItemType
from app.schemas.pagination import PaginationParams

_MIN_SEARCH_TERM_LENGTH = 2
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class AreaPoint:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class PostVisibilityScope:
    include_unpublished: bool = False
    owner_id: UUID | None = None
    viewer_is_adult: bool = False
    member_id: UUID | None = None


def _community_visible_in(scope: PostVisibilityScope) -> ColumnElement[bool]:
    author_is_blocked = exists().where(
        CommunityMember.community_id == Post.community_id,
        CommunityMember.user_id == Post.user_id,
        CommunityMember.status == CommunityMemberStatus.BLOCKED,
    )
    is_public = Post.visibility == PostVisibility.PUBLIC
    if scope.member_id is None:
        return or_(Post.community_id.is_(None), is_public & ~author_is_blocked)
    active_communities = select(CommunityMember.community_id).where(
        CommunityMember.user_id == scope.member_id,
        CommunityMember.status == CommunityMemberStatus.ACTIVE,
    )
    return or_(
        Post.community_id.is_(None),
        (is_public | Post.community_id.in_(active_communities)) & ~author_is_blocked,
    )


def _visible_in(scope: PostVisibilityScope) -> ColumnElement[bool]:
    not_deleted = Post.deleted_at.is_(None)
    if scope.include_unpublished:
        return not_deleted
    published = Post.status == PostStatus.PUBLISHED
    suitable_audience = Post.audience == PostAudience.EVERYONE
    if scope.viewer_is_adult:
        suitable_audience = true()
    in_visible_community = _community_visible_in(scope)
    if scope.owner_id is None:
        return not_deleted & published & suitable_audience & in_visible_community
    is_owner = Post.user_id == scope.owner_id
    return not_deleted & in_visible_community & or_(published & suitable_audience, is_owner)


def _order_by_recency() -> tuple[ColumnElement[Any], ...]:
    return (Post.created_at.desc(),)


def _order_by_likes() -> tuple[ColumnElement[Any], ...]:
    return (Post.likes_count.desc(), Post.created_at.desc())


def _has_tag_matching(predicate: ColumnElement[bool]) -> ColumnElement[bool]:
    return exists(
        select(1)
        .select_from(post_tags)
        .join(Tag, Tag.id == post_tags.c.tag_id)
        .where(post_tags.c.post_id == Post.id, predicate)
    )


def _search_terms(query: str) -> list[str]:
    words = _WHITESPACE.split(query.strip())
    terms = [word for word in words if len(word) >= _MIN_SEARCH_TERM_LENGTH]
    return terms or [query.strip()]


def _term_matches(term: str) -> ColumnElement[bool]:
    pattern = f"%{term}%"
    return or_(
        Post.title.ilike(pattern),
        Post.content.ilike(pattern),
        _has_tag_matching(Tag.name.ilike(pattern)),
    )


def _location_matches(location: str) -> ColumnElement[bool]:
    pattern = f"%{location}%"
    return or_(
        Post.location_name.ilike(pattern),
        Post.title.ilike(pattern),
        Post.content.ilike(pattern),
    )


def _match_score(term_conditions: list[ColumnElement[bool]]) -> ColumnElement[int]:
    parts = [case((condition, 1), else_=0) for condition in term_conditions]
    score: ColumnElement[int] = parts[0]
    for part in parts[1:]:
        score = score + part
    return score


class PostRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, post_id: UUID) -> Post | None:
        return self._db.scalar(select(Post).where(Post.id == post_id, Post.deleted_at.is_(None)))

    def get_visible_by_id(self, post_id: UUID, scope: PostVisibilityScope) -> Post | None:
        return self._db.scalar(select(Post).where(Post.id == post_id, _visible_in(scope)))

    def get_visible_by_slug(self, slug: str, scope: PostVisibilityScope) -> Post | None:
        return self._db.scalar(select(Post).where(Post.slug == slug, _visible_in(scope)))

    def exists_with_title(
        self, user_id: UUID, title: str, exclude_post_id: UUID | None = None
    ) -> bool:
        conditions: list[ColumnElement[bool]] = [
            Post.user_id == user_id,
            Post.deleted_at.is_(None),
            Post.title == title,
        ]
        if exclude_post_id is not None:
            conditions.append(Post.id != exclude_post_id)
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def exists_with_content(
        self, user_id: UUID, content: str, exclude_post_id: UUID | None = None
    ) -> bool:
        conditions: list[ColumnElement[bool]] = [
            Post.user_id == user_id,
            Post.deleted_at.is_(None),
            Post.content == content,
        ]
        if exclude_post_id is not None:
            conditions.append(Post.id != exclude_post_id)
        return bool(self._db.scalar(select(exists().where(*conditions))))

    def list_for_admin(
        self,
        params: PaginationParams,
        status: PostStatus | None = None,
        audience: PostAudience | None = None,
        visibility: PostVisibility | None = None,
        user_id: UUID | None = None,
        community_id: UUID | None = None,
        query: str | None = None,
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [Post.deleted_at.is_(None)]
        if status is not None:
            conditions.append(Post.status == status)
        if audience is not None:
            conditions.append(Post.audience == audience)
        if visibility is not None:
            conditions.append(Post.visibility == visibility)
        if user_id is not None:
            conditions.append(Post.user_id == user_id)
        if community_id is not None:
            conditions.append(Post.community_id == community_id)
        stripped_query = query.strip() if query else None
        if stripped_query:
            conditions.append(or_(*(_term_matches(term) for term in _search_terms(stripped_query))))
        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .where(*conditions)
            .order_by(*_order_by_recency(), Post.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_by_community(
        self,
        community_id: UUID,
        params: PaginationParams,
        scope: PostVisibilityScope,
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [
            _visible_in(scope),
            Post.community_id == community_id,
        ]
        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .where(*conditions)
            .order_by(*_order_by_recency())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def timeline_entries(
        self,
        community_id: UUID,
        scope: PostVisibilityScope,
    ) -> Select[*tuple[Any, ...]]:
        return select(
            Post.id.label("id"),
            Post.published_at.label("sort_at"),
            literal(TimelineItemType.POST.value).label("kind"),
        ).where(
            _visible_in(scope),
            Post.community_id == community_id,
            Post.status == PostStatus.PUBLISHED,
            Post.published_at.is_not(None),
        )

    def list_by_ids(self, post_ids: Sequence[UUID]) -> list[Post]:
        return list(
            self._db.scalars(select(Post).where(Post.id.in_(post_ids), Post.deleted_at.is_(None)))
        )

    def get_in_community(self, community_id: UUID, post_id: UUID) -> Post | None:
        return self._db.scalar(
            select(Post).where(
                Post.id == post_id,
                Post.community_id == community_id,
                Post.deleted_at.is_(None),
            )
        )

    def soft_remove(self, post: Post, removed_by: UUID, reason: str) -> None:
        post.deleted_at = app_now()
        post.removed_by = removed_by
        post.removal_reason = reason
        self._db.commit()

    def list_by_user(
        self,
        user_id: UUID,
        params: PaginationParams,
        scope: PostVisibilityScope,
        order_by_likes: bool = False,
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope), Post.user_id == user_id]
        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        order = _order_by_likes() if order_by_likes else _order_by_recency()
        items = self._db.scalars(
            select(Post).where(*conditions).order_by(*order).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total

    def search(
        self,
        params: PaginationParams,
        scope: PostVisibilityScope,
        tag_slugs: list[str] | None = None,
        query: str | None = None,
        order_by_likes: bool = False,
        location: str | None = None,
        match_any_term: bool = False,
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope)]

        stripped_location = location.strip() if location else None
        if stripped_location:
            conditions.append(_location_matches(stripped_location))

        match_filters: list[ColumnElement[bool]] = []
        relevance: ColumnElement[int] | None = None
        if tag_slugs:
            match_filters.append(_has_tag_matching(Tag.slug.in_(tag_slugs)))

        stripped_query = query.strip() if query else None
        if stripped_query:
            terms = _search_terms(stripped_query)
            term_conditions = [_term_matches(term) for term in terms]
            relevance = _match_score(term_conditions)
            # A query is usually several loosely-related words; matching just one of
            # them (e.g. "kerala") shouldn't qualify a post that's otherwise
            # unrelated, so require at least two matches once there's more than one
            # term to check.
            min_matches = 2 if len(term_conditions) > 1 and not match_any_term else 1
            match_filters.append(relevance >= min_matches)

        if match_filters:
            conditions.append(or_(*match_filters))

        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        secondary_order = _order_by_likes() if order_by_likes else _order_by_recency()
        order = (relevance.desc(), *secondary_order) if relevance is not None else secondary_order
        items = self._db.scalars(
            select(Post).where(*conditions).order_by(*order).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total

    def search_nearby(
        self,
        latitude: float,
        longitude: float,
        radius_meters: int,
        scope: PostVisibilityScope,
        limit: int,
    ) -> list[tuple[Post, float]]:
        point = cast(func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326), Geography)
        location = cast(Post.location, Geography)
        distance = func.ST_Distance(location, point).label("distance_meters")
        rows = self._db.execute(
            select(Post, distance)
            .where(
                _visible_in(scope),
                func.ST_DWithin(location, point, radius_meters),
            )
            .order_by(distance.asc(), Post.created_at.desc())
            .limit(limit)
        ).all()
        return [(post, distance_meters) for post, distance_meters in rows]

    def exists_visible_within(
        self, latitude: float, longitude: float, radius_meters: int, scope: PostVisibilityScope
    ) -> bool:
        point = as_geography(point_from_coordinates(latitude, longitude))
        within = func.ST_DWithin(as_geography(Post.location), point, radius_meters)
        return bool(self._db.scalar(select(exists().where(_visible_in(scope), within))))

    def list_saved_by_user(
        self, user_id: UUID, params: PaginationParams, scope: PostVisibilityScope
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope), SavedPost.user_id == user_id]
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(Post)
                .join(SavedPost, SavedPost.post_id == Post.id)
                .where(*conditions)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .join(SavedPost, SavedPost.post_id == Post.id)
            .where(*conditions)
            .order_by(SavedPost.created_at.desc(), SavedPost.id.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_by_collection(
        self, collection_id: UUID, params: PaginationParams, scope: PostVisibilityScope
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [
            _visible_in(scope),
            CollectionPost.collection_id == collection_id,
        ]
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(Post)
                .join(SavedPost, SavedPost.post_id == Post.id)
                .join(CollectionPost, CollectionPost.saved_post_id == SavedPost.id)
                .where(*conditions)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .join(SavedPost, SavedPost.post_id == Post.id)
            .join(CollectionPost, CollectionPost.saved_post_id == SavedPost.id)
            .where(*conditions)
            .order_by(CollectionPost.created_at.desc(), CollectionPost.id.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list(
        self,
        params: PaginationParams,
        scope: PostVisibilityScope,
        user_id: UUID | None = None,
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope)]
        if user_id is not None:
            conditions.append(Post.user_id == user_id)
        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Post)
            .where(*conditions)
            .order_by(Post.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_nearby(
        self,
        params: PaginationParams,
        scope: PostVisibilityScope,
        latitude: float,
        longitude: float,
        radius_meters: float | None,
        query: str | None = None,
        user_id: UUID | None = None,
        priority_radius_meters: float | None = None,
    ) -> tuple[Sequence[tuple[Post, float]], int]:
        point = as_geography(point_from_coordinates(latitude, longitude))
        location = as_geography(Post.location)
        distance = func.ST_Distance(location, point).label("distance_meters")
        conditions: list[ColumnElement[bool]] = [_visible_in(scope), Post.location.is_not(None)]
        if user_id is not None:
            conditions.append(Post.user_id == user_id)
        stripped_query = query.strip() if query else None
        if stripped_query:
            conditions.append(or_(*(_term_matches(term) for term in _search_terms(stripped_query))))
        if radius_meters is not None:
            conditions.append(func.ST_DWithin(location, point, radius_meters))
        total = self._db.scalar(select(func.count()).select_from(Post).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        order: list[Any] = [distance.asc(), Post.created_at.desc(), Post.id.asc()]
        if priority_radius_meters is not None:
            within_priority = distance <= priority_radius_meters
            order = [
                case((within_priority, 0), else_=1),
                case((within_priority, Post.created_at)).desc().nulls_last(),
                *order,
            ]
        rows = self._db.execute(
            select(Post, distance)
            .where(*conditions)
            .order_by(*order)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [(post, distance_meters) for post, distance_meters in rows], total

    def list_for_areas(
        self,
        params: PaginationParams,
        scope: PostVisibilityScope,
        areas: Sequence[AreaPoint],
        radius_meters: float,
    ) -> tuple[Sequence[tuple[Post, int, float]], int]:
        anchor = as_geography(func.coalesce(Post.location, func.ST_PointOnSurface(GisVillage.geom)))
        points = [as_geography(point_from_coordinates(a.latitude, a.longitude)) for a in areas]
        within = [func.ST_DWithin(anchor, point, radius_meters) for point in points]
        rank = case(*((condition, index) for index, condition in enumerate(within)), else_=-1)
        distance = case(
            *(
                (condition, func.ST_Distance(anchor, point))
                for condition, point in zip(within, points, strict=True)
            )
        )
        conditions: list[ColumnElement[bool]] = [
            _visible_in(scope),
            Post.status == PostStatus.PUBLISHED,
            or_(Post.community_id.is_(None), Community.status == CommunityStatus.PUBLISHED),
            or_(*within),
        ]
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(Post)
                .outerjoin(Community, Community.id == Post.community_id)
                .outerjoin(GisVillage, GisVillage.id == Community.village_id)
                .where(*conditions)
            )
            or 0
        )
        offset = (params.page - 1) * params.page_size
        rows = self._db.execute(
            select(Post, rank.label("area_rank"), distance.label("distance_meters"))
            .outerjoin(Community, Community.id == Post.community_id)
            .outerjoin(GisVillage, GisVillage.id == Community.village_id)
            .where(*conditions)
            .order_by(rank, Post.created_at.desc(), Post.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [(post, area_rank, meters) for post, area_rank, meters in rows], total

    def add(self, post: Post) -> Post:
        self._db.add(post)
        self._db.commit()
        self._db.refresh(post)
        return post

    def save(self, post: Post) -> Post:
        self._db.commit()
        self._db.refresh(post)
        return post

    def soft_delete(self, post: Post) -> None:
        post.deleted_at = app_now()
        self._db.commit()

    def increment_likes(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.likes_count, 1)

    def decrement_likes(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.likes_count, -1)

    def increment_comments(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.comments_count, 1)

    def decrement_comments(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.comments_count, -1)

    def increment_shares(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.shares_count, 1)

    def increment_saved(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.saved_count, 1)

    def decrement_saved(self, post_id: UUID) -> None:
        self._adjust_count(post_id, Post.saved_count, -1)

    def _adjust_count(self, post_id: UUID, column: InstrumentedAttribute[int], delta: int) -> None:
        self._db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values({column: func.greatest(column + delta, 0)})
        )
        self._db.commit()
