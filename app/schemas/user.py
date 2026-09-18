from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserStatus, UserType
from app.schemas.role import RoleSummary, RoleWithPermissions


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    profile_image_url: str | None
    status: UserStatus
    roles: list[RoleSummary]


class AuthenticatedUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    profile_image_url: str | None
    status: UserStatus
    roles: list[RoleWithPermissions]


class UserRolesAssign(BaseModel):
    role_ids: list[UUID]


class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    password: str


class UserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: UserStatus | None = None
    user_type: UserType | None = None


class UserSelfUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
