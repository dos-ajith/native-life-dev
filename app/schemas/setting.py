from uuid import UUID

from pydantic import BaseModel, ConfigDict


class SettingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    key: str
    value: str | None


class SettingCreate(BaseModel):
    key: str
    value: str | None = None


class SettingUpdate(BaseModel):
    key: str | None = None
    value: str | None = None
