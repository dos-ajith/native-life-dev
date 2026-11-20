from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.messages import ActivityLogMessages
from app.schemas.base import BaseReadSchema

ACTION_MAX_LENGTH = 100
ENTITY_TYPE_MAX_LENGTH = 100


class ActivityLogQuery(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: str | None = Field(default=None, max_length=ACTION_MAX_LENGTH)
    user_id: UUID | None = None
    entity_type: str | None = Field(default=None, max_length=ENTITY_TYPE_MAX_LENGTH)
    entity_id: UUID | None = None
    date_from: date | None = None
    date_to: date | None = None

    @model_validator(mode="after")
    def _ordered_dates(self) -> "ActivityLogQuery":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError(ActivityLogMessages.DATE_RANGE_INVALID)
        return self


class ActivityActorRead(BaseModel):
    id: UUID
    name: str
    email: str | None


class ActivityLogRead(BaseReadSchema):
    id: UUID
    actor: ActivityActorRead | None
    action: str
    entity_type: str | None
    entity_id: UUID | None
    description: str | None
    metadata: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None
    created_at: datetime
