from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.plugins.sdk import BaseReadSchema

from ..config import MAX_STOCK_QUANTITY

CurrencyCode = Annotated[str, Field(pattern=r"^[A-Z]{3}$")]


class SettingsUpdate(BaseModel):
    currency: CurrencyCode | None = None
    default_low_stock_threshold: Annotated[int, Field(ge=0, le=MAX_STOCK_QUANTITY)] | None = None


class SettingsRead(BaseReadSchema):
    business_id: UUID
    currency: str
    default_low_stock_threshold: int
    updated_at: datetime | None = None
