from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.permission import PermissionRead, PermissionSummary
from app.schemas.validators import NonBlankStr

RoleName = Annotated[NonBlankStr, Field(max_length=100)]
RoleDescription = Annotated[str, Field(max_length=255)]


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    description: str | None
    permissions: list[PermissionRead]


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str


class RoleWithPermissions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    slug: str
    permissions: list[PermissionSummary]


class RoleCreate(BaseModel):
    name: RoleName
    description: RoleDescription | None = None


class RoleUpdate(BaseModel):
    name: RoleName | None = None
    description: RoleDescription | None = None
