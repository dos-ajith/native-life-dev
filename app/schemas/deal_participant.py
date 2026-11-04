from datetime import datetime
from typing import TYPE_CHECKING

from app.schemas.base import BaseReadSchema
from app.schemas.post import PostAuthorRead

if TYPE_CHECKING:
    from app.models.deal_participant import DealParticipant


class DealParticipantRead(BaseReadSchema):
    user: PostAuthorRead
    joined_at: datetime
    order_count: int

    @classmethod
    def from_participant(
        cls, participant: "DealParticipant", order_count: int
    ) -> "DealParticipantRead":
        return cls(
            user=PostAuthorRead.from_user(participant.user),
            joined_at=participant.created_at,
            order_count=order_count,
        )
