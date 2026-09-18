from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.validators import NonBlankStr

SettingKey = Annotated[NonBlankStr, Field(max_length=150)]


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    value: str | None


class SettingCreate(BaseModel):
    key: SettingKey
    value: str | None = None


class SettingUpdate(BaseModel):
    key: SettingKey | None = None
    value: str | None = None
