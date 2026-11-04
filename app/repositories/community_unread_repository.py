from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session, aliased

from app.models.community_member import CommunityMember, CommunityMemberStatus
from app.models.community_message import CommunityMessage
from app.models.community_poll import CommunityPoll
from app.models.post import Post, PostStatus


class CommunityUnreadRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def counts_for(self, user_id: UUID, community_ids: Sequence[UUID]) -> dict[UUID, int]:
        counts: dict[UUID, int] = {}
        for community_id, total in (
            *self._message_counts(user_id, community_ids),
            *self._poll_counts(user_id, community_ids),
            *self._post_counts(user_id, community_ids),
        ):
            counts[community_id] = counts.get(community_id, 0) + total
        return counts

    def _message_counts(
        self, user_id: UUID, community_ids: Sequence[UUID]
    ) -> list[tuple[UUID, int]]:
        read_marker = func.coalesce(CommunityMember.last_read_at, CommunityMember.created_at)
        rows = self._db.execute(
            select(CommunityMessage.community_id, func.count())
            .join(
                CommunityMember,
                and_(
                    CommunityMember.community_id == CommunityMessage.community_id,
                    CommunityMember.user_id == user_id,
                    CommunityMember.status == CommunityMemberStatus.ACTIVE,
                ),
            )
            .where(
                CommunityMessage.community_id.in_(community_ids),
                CommunityMessage.sender_id != user_id,
                CommunityMessage.created_at > read_marker,
            )
            .group_by(CommunityMessage.community_id)
        ).all()
        return [(community_id, total) for community_id, total in rows]

    def _poll_counts(self, user_id: UUID, community_ids: Sequence[UUID]) -> list[tuple[UUID, int]]:
        read_marker = func.coalesce(CommunityMember.last_read_at, CommunityMember.created_at)
        rows = self._db.execute(
            select(CommunityPoll.community_id, func.count())
            .join(
                CommunityMember,
                and_(
                    CommunityMember.community_id == CommunityPoll.community_id,
                    CommunityMember.user_id == user_id,
                    CommunityMember.status == CommunityMemberStatus.ACTIVE,
                ),
            )
            .where(
                CommunityPoll.community_id.in_(community_ids),
                CommunityPoll.author_id != user_id,
                CommunityPoll.created_at > read_marker,
            )
            .group_by(CommunityPoll.community_id)
        ).all()
        return [(community_id, total) for community_id, total in rows]

    def _post_counts(self, user_id: UUID, community_ids: Sequence[UUID]) -> list[tuple[UUID, int]]:
        read_marker = func.coalesce(CommunityMember.last_read_at, CommunityMember.created_at)
        author_membership = aliased(CommunityMember)
        author_is_blocked = exists().where(
            author_membership.community_id == Post.community_id,
            author_membership.user_id == Post.user_id,
            author_membership.status == CommunityMemberStatus.BLOCKED,
        )
        rows = self._db.execute(
            select(Post.community_id, func.count())
            .join(
                CommunityMember,
                and_(
                    CommunityMember.community_id == Post.community_id,
                    CommunityMember.user_id == user_id,
                    CommunityMember.status == CommunityMemberStatus.ACTIVE,
                ),
            )
            .where(
                Post.community_id.in_(community_ids),
                Post.user_id != user_id,
                Post.deleted_at.is_(None),
                Post.status == PostStatus.PUBLISHED,
                Post.published_at > read_marker,
                ~author_is_blocked,
            )
            .group_by(Post.community_id)
        ).all()
        return [(community_id, total) for community_id, total in rows if community_id is not None]
