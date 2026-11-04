from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PresenceRead(BaseModel):
    user_id: UUID
    visible: bool
    is_online: bool | None
    last_seen_at: datetime | None
