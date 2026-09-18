from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.permission import PermissionRead, PermissionSummary


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    permissions: list[PermissionRead]


class RoleSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class RoleWithPermissions(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    permissions: list[PermissionSummary]


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RolePermissionsAssign(BaseModel):
    permission_ids: list[UUID]
