import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import ColumnElement, case, cast, exists, func, or_, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.models.collection_post import CollectionPost
from app.models.post import Post, PostStatus
from app.models.post_tag import post_tags
from app.models.saved_post import SavedPost
from app.models.tag import Tag
from app.schemas.pagination import PaginationParams

_MIN_SEARCH_TERM_LENGTH = 2
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class PostVisibilityScope:
    include_unpublished: bool = False
    owner_id: UUID | None = None


def _visible_in(scope: PostVisibilityScope) -> ColumnElement[bool]:
    not_deleted = Post.deleted_at.is_(None)
    if scope.include_unpublished:
        return not_deleted
    published = Post.status == PostStatus.PUBLISHED
    if scope.owner_id is None:
        return not_deleted & published
    return not_deleted & or_(published, Post.user_id == scope.owner_id)


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
        return self._db.scalar(
            select(Post).where(Post.id == post_id, Post.deleted_at.is_(None))
        )

    def get_visible_by_id(self, post_id: UUID, scope: PostVisibilityScope) -> Post | None:
        return self._db.scalar(select(Post).where(Post.id == post_id, _visible_in(scope)))

    def get_visible_by_slug(self, slug: str, scope: PostVisibilityScope) -> Post | None:
        return self._db.scalar(select(Post).where(Post.slug == slug, _visible_in(scope)))

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
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope)]

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
            min_matches = 2 if len(term_conditions) > 1 else 1
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
        self, params: PaginationParams, scope: PostVisibilityScope
    ) -> tuple[list[Post], int]:
        conditions: list[ColumnElement[bool]] = [_visible_in(scope)]
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
        post.deleted_at = datetime.now(UTC)
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

    def _adjust_count(
        self, post_id: UUID, column: InstrumentedAttribute[int], delta: int
    ) -> None:
        self._db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values({column: func.greatest(column + delta, 0)})
        )
        self._db.commit()
