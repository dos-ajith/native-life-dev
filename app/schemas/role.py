from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.permission import PermissionRead


class RoleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None
    permissions: list[PermissionRead]


class RoleCreate(BaseModel):
    name: str
    description: str | None = None


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RolePermissionsAssign(BaseModel):
    permission_ids: list[UUID]
