from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.validators import NonBlankStr

PermissionName = Annotated[NonBlankStr, Field(max_length=150)]
PermissionDescription = Annotated[str, Field(max_length=255)]


class PermissionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None


class PermissionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class PermissionCreate(BaseModel):
    name: PermissionName
    description: PermissionDescription | None = None


class PermissionUpdate(BaseModel):
    name: PermissionName | None = None
    description: PermissionDescription | None = None
