from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Select, delete, func, literal, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.community_poll import CommunityPoll, CommunityPollOption, CommunityPollVote
from app.schemas.community_timeline import TimelineItemType
from app.schemas.pagination import PaginationParams

_WITH_DETAILS = (selectinload(CommunityPoll.options), selectinload(CommunityPoll.author))


class CommunityPollRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, poll: CommunityPoll) -> CommunityPoll:
        self._db.add(poll)
        self._db.commit()
        self._db.refresh(poll)
        return poll

    def get_by_id(self, poll_id: UUID) -> CommunityPoll | None:
        return self._db.scalar(
            select(CommunityPoll)
            .options(*_WITH_DETAILS)
            .where(CommunityPoll.id == poll_id)
            .execution_options(populate_existing=True)
        )

    def get_for_update(self, poll_id: UUID) -> CommunityPoll | None:
        return self._db.scalar(
            select(CommunityPoll)
            .options(*_WITH_DETAILS)
            .where(CommunityPoll.id == poll_id)
            .with_for_update(of=CommunityPoll)
            .execution_options(populate_existing=True)
        )

    def list_by_ids(self, poll_ids: Sequence[UUID]) -> list[CommunityPoll]:
        return list(
            self._db.scalars(
                select(CommunityPoll)
                .options(*_WITH_DETAILS)
                .where(CommunityPoll.id.in_(poll_ids))
                .execution_options(populate_existing=True)
            )
        )

    def list_for_community(
        self, community_id: UUID, params: PaginationParams
    ) -> tuple[list[CommunityPoll], int]:
        condition = CommunityPoll.community_id == community_id
        total = self._db.scalar(select(func.count()).select_from(CommunityPoll).where(condition))
        offset = (params.page - 1) * params.page_size
        polls = self._db.scalars(
            select(CommunityPoll)
            .options(*_WITH_DETAILS)
            .where(condition)
            .order_by(CommunityPoll.created_at.desc(), CommunityPoll.id.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(polls), total or 0

    def timeline_entries(self, community_id: UUID) -> Select[*tuple[Any, ...]]:
        return select(
            CommunityPoll.id.label("id"),
            CommunityPoll.created_at.label("sort_at"),
            literal(TimelineItemType.POLL.value).label("kind"),
        ).where(CommunityPoll.community_id == community_id)

    def list_user_option_ids(
        self, user_id: UUID, poll_ids: Sequence[UUID]
    ) -> dict[UUID, list[UUID]]:
        rows = self._db.execute(
            select(CommunityPollVote.poll_id, CommunityPollVote.option_id).where(
                CommunityPollVote.user_id == user_id, CommunityPollVote.poll_id.in_(poll_ids)
            )
        ).all()
        chosen: dict[UUID, list[UUID]] = {}
        for poll_id, option_id in rows:
            chosen.setdefault(poll_id, []).append(option_id)
        return chosen

    def stage_votes(self, poll_id: UUID, user_id: UUID, option_ids: Sequence[UUID]) -> None:
        self._db.add_all(
            CommunityPollVote(poll_id=poll_id, option_id=option_id, user_id=user_id)
            for option_id in option_ids
        )
        self._adjust_counts(option_ids, 1)

    def stage_vote_removals(self, poll_id: UUID, user_id: UUID, option_ids: Sequence[UUID]) -> None:
        if not option_ids:
            return
        self._db.execute(
            delete(CommunityPollVote).where(
                CommunityPollVote.poll_id == poll_id,
                CommunityPollVote.user_id == user_id,
                CommunityPollVote.option_id.in_(option_ids),
            )
        )
        self._adjust_counts(option_ids, -1)

    def commit(self) -> None:
        self._db.commit()

    def _adjust_counts(self, option_ids: Sequence[UUID], delta: int) -> None:
        if not option_ids:
            return
        self._db.execute(
            update(CommunityPollOption)
            .where(CommunityPollOption.id.in_(option_ids))
            .values(votes_count=CommunityPollOption.votes_count + delta)
            .execution_options(synchronize_session=False)
        )
