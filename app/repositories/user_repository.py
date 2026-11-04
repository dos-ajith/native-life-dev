from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Exists, ScalarSelect, func, or_, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session, aliased

from app.core.timezone import app_now
from app.models.permission import Permission
from app.models.post import Post, PostStatus
from app.models.role import Role
from app.models.user import User, UserStatus
from app.models.user_follow import UserFollow
from app.models.user_follow_request import UserFollowRequest
from app.schemas.pagination import PaginationParams


@dataclass(frozen=True)
class UserDiscoveryRow:
    id: UUID
    first_name: str
    last_name: str
    profile_image_url: str | None
    followers_count: int
    following_count: int
    is_following: bool
    is_requested: bool


@dataclass(frozen=True)
class UserProfileRow:
    id: UUID
    first_name: str
    last_name: str
    profile_image_url: str | None
    followers_count: int
    following_count: int
    posts_count: int
    is_following: bool
    is_followed_by: bool
    is_requested: bool


def _followers_count() -> ScalarSelect[int]:
    follower = aliased(User)
    return (
        select(func.count())
        .select_from(UserFollow)
        .join(follower, follower.id == UserFollow.follower_id)
        .where(UserFollow.following_id == User.id, follower.deleted_at.is_(None))
        .scalar_subquery()
    )


def _following_count() -> ScalarSelect[int]:
    followed = aliased(User)
    return (
        select(func.count())
        .select_from(UserFollow)
        .join(followed, followed.id == UserFollow.following_id)
        .where(UserFollow.follower_id == User.id, followed.deleted_at.is_(None))
        .scalar_subquery()
    )


def _follows(
    follower_id: UUID | InstrumentedAttribute[UUID],
    following_id: UUID | InstrumentedAttribute[UUID],
) -> Exists:
    return (
        select(UserFollow.id)
        .where(UserFollow.follower_id == follower_id, UserFollow.following_id == following_id)
        .exists()
    )


class UserRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        return self._db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None)))

    def get_by_phone(self, phone: str) -> User | None:
        return self._db.scalar(select(User).where(User.phone == phone, User.deleted_at.is_(None)))

    def get_by_email_ignoring_case(self, email: str) -> User | None:
        return self._db.scalar(
            select(User).where(func.lower(User.email) == email.lower(), User.deleted_at.is_(None))
        )

    def get_by_verified_phone(self, phone: str) -> User | None:
        return self._db.scalar(
            select(User).where(
                User.phone == phone,
                User.phone_verified_at.is_not(None),
                User.deleted_at.is_(None),
            )
        )

    def list_unverified_by_phone(self, phone: str) -> list[User]:
        return list(
            self._db.scalars(
                select(User).where(
                    User.phone == phone,
                    User.phone_verified_at.is_(None),
                    User.deleted_at.is_(None),
                )
            )
        )

    def get_by_id(self, user_id: UUID) -> User | None:
        return self._db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))

    def get_by_id_including_deleted(self, user_id: UUID) -> User | None:
        return self._db.get(User, user_id)

    def get_by_ids_including_deleted(self, user_ids: list[UUID]) -> list[User]:
        return list(self._db.scalars(select(User).where(User.id.in_(user_ids))))

    def list_active_with_permission(
        self, permission_names: Sequence[str], unrestricted_role_slugs: frozenset[str]
    ) -> list[User]:
        return list(
            self._db.scalars(
                select(User)
                .where(
                    User.deleted_at.is_(None),
                    User.status == UserStatus.ACTIVE,
                    User.roles.any(
                        or_(
                            Role.slug.in_(unrestricted_role_slugs),
                            Role.permissions.any(Permission.name.in_(permission_names)),
                        )
                    ),
                )
                .distinct()
            )
        )

    def list(self, params: PaginationParams) -> tuple[list[User], int]:
        not_deleted = User.deleted_at.is_(None)
        total = self._db.scalar(select(func.count()).select_from(User).where(not_deleted)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(User)
            .where(not_deleted)
            .order_by(User.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def list_discoverable(
        self, viewer_id: UUID, search: str | None, params: PaginationParams
    ) -> tuple[Sequence[UserDiscoveryRow], int]:
        conditions = [
            User.deleted_at.is_(None),
            User.status == UserStatus.ACTIVE,
            User.id != viewer_id,
        ]
        if search:
            full_name = User.first_name + " " + User.last_name
            conditions.append(full_name.icontains(search, autoescape=True))
        total = self._db.scalar(select(func.count()).select_from(User).where(*conditions)) or 0
        followers_count = _followers_count()
        following_count = _following_count()
        is_following = _follows(viewer_id, User.id)
        is_requested = (
            select(UserFollowRequest.id)
            .where(
                UserFollowRequest.requester_id == viewer_id,
                UserFollowRequest.target_id == User.id,
            )
            .exists()
        )
        offset = (params.page - 1) * params.page_size
        rows = self._db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.profile_image_url,
                followers_count.label("followers_count"),
                following_count.label("following_count"),
                is_following.label("is_following"),
                is_requested.label("is_requested"),
            )
            .where(*conditions)
            .order_by(User.first_name, User.last_name, User.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [UserDiscoveryRow(*row) for row in rows], total

    def get_profile(self, viewer_id: UUID, user_id: UUID) -> UserProfileRow | None:
        posts_count = (
            select(func.count())
            .select_from(Post)
            .where(
                Post.user_id == User.id,
                Post.status == PostStatus.PUBLISHED,
                Post.deleted_at.is_(None),
            )
            .scalar_subquery()
        )
        is_requested = (
            select(UserFollowRequest.id)
            .where(
                UserFollowRequest.requester_id == viewer_id,
                UserFollowRequest.target_id == User.id,
            )
            .exists()
        )
        row = self._db.execute(
            select(
                User.id,
                User.first_name,
                User.last_name,
                User.profile_image_url,
                _followers_count().label("followers_count"),
                _following_count().label("following_count"),
                posts_count.label("posts_count"),
                _follows(viewer_id, User.id).label("is_following"),
                _follows(User.id, viewer_id).label("is_followed_by"),
                is_requested.label("is_requested"),
            ).where(
                User.id == user_id,
                User.deleted_at.is_(None),
                User.status == UserStatus.ACTIVE,
            )
        ).first()
        if row is None:
            return None
        return UserProfileRow(
            id=row.id,
            first_name=row.first_name,
            last_name=row.last_name,
            profile_image_url=row.profile_image_url,
            followers_count=row.followers_count,
            following_count=row.following_count,
            posts_count=row.posts_count,
            is_following=row.is_following,
            is_followed_by=row.is_followed_by,
            is_requested=row.is_requested,
        )

    def add(self, user: User) -> User:
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user

    def stage(self, user: User) -> User:
        self._db.add(user)
        self._db.flush()
        return user

    def save(self, user: User) -> User:
        self._db.commit()
        self._db.refresh(user)
        return user

    def lock(self, user: User) -> None:
        self._db.refresh(user, with_for_update=True)
        self._db.expire(user, ["roles"])

    def touch_last_seen(self, user_id: UUID) -> None:
        self._db.execute(update(User).where(User.id == user_id).values(last_seen_at=func.now()))
        self._db.commit()

    def soft_delete(self, user: User) -> None:
        user.deleted_at = app_now()
        self._db.commit()
