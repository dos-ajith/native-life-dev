from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.core.messages import PollMessages
from app.schemas.validators import NonBlankStr

MIN_POLL_OPTIONS = 2
MAX_POLL_OPTIONS = 6
MAX_POLL_OPTION_LENGTH = 200

PollOptionText = Annotated[NonBlankStr, Field(max_length=MAX_POLL_OPTION_LENGTH)]


class PollCreate(BaseModel):
    options: list[PollOptionText] = Field(min_length=MIN_POLL_OPTIONS, max_length=MAX_POLL_OPTIONS)
    allows_multiple: bool = False
    show_results_before_vote: bool = False
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def _validate_unique_options(self) -> "PollCreate":
        normalized = {option.casefold() for option in self.options}
        if len(normalized) != len(self.options):
            raise ValueError(PollMessages.DUPLICATE_OPTIONS)
        return self


class PollVoteRequest(BaseModel):
    option_ids: list[UUID] = Field(min_length=1, max_length=MAX_POLL_OPTIONS)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> "PollVoteRequest":
        if len(set(self.option_ids)) != len(self.option_ids):
            raise ValueError(PollMessages.DUPLICATE_OPTION_IDS)
        return self


class PollOptionRead(BaseModel):
    id: UUID
    text: str
    position: int
    votes_count: int | None
