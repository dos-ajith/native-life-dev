from collections.abc import Sequence
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field

from app.models.community_poll import CommunityPoll
from app.schemas.base import BaseReadSchema
from app.schemas.poll import PollCreate, PollOptionRead
from app.schemas.post import PostAuthorRead
from app.schemas.validators import NonBlankStr
from app.utils.relative_time import format_relative_time

MAX_QUESTION_LENGTH = 500

PollQuestion = Annotated[NonBlankStr, Field(max_length=MAX_QUESTION_LENGTH)]


class CommunityPollCreate(PollCreate):
    question: PollQuestion


class CommunityPollRead(BaseReadSchema):
    id: UUID
    author: PostAuthorRead
    question: str
    created_at: datetime
    created_at_relative: str
    allows_multiple: bool
    show_results_before_vote: bool
    ends_at: datetime | None
    is_closed: bool
    options: list[PollOptionRead]
    my_option_ids: list[UUID]
    total_votes: int | None

    @classmethod
    def from_poll(
        cls, poll: CommunityPoll, my_option_ids: Sequence[UUID], viewer_id: UUID
    ) -> "CommunityPollRead":
        shows_results = (
            poll.is_closed
            or poll.show_results_before_vote
            or bool(my_option_ids)
            or poll.author_id == viewer_id
        )
        return cls(
            id=poll.id,
            author=PostAuthorRead.from_user(poll.author),
            question=poll.question,
            created_at=poll.created_at,
            created_at_relative=format_relative_time(poll.created_at),
            allows_multiple=poll.allows_multiple,
            show_results_before_vote=poll.show_results_before_vote,
            ends_at=poll.ends_at,
            is_closed=poll.is_closed,
            options=[
                PollOptionRead(
                    id=option.id,
                    text=option.text,
                    position=option.position,
                    votes_count=option.votes_count if shows_results else None,
                )
                for option in poll.options
            ],
            my_option_ids=list(my_option_ids),
            total_votes=(
                sum(option.votes_count for option in poll.options) if shows_results else None
            ),
        )
