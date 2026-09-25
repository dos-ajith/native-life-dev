from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import UserStatus, UserType
from app.schemas.role import RoleSummary, RoleWithPermissions
from app.schemas.validators import NameStr

PHONE_PATTERN = r"^\+?[0-9]{7,15}$"

Name = Annotated[NameStr, Field(max_length=100)]
Email = Annotated[EmailStr, Field(max_length=255)]
Phone = Annotated[str, Field(max_length=30, pattern=PHONE_PATTERN)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


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


class UserCreate(BaseModel):
    first_name: Name
    last_name: Name
    email: Email
    phone: Phone | None = None
    password: Password


class UserUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    email: Email | None = None
    phone: Phone | None = None
    status: UserStatus | None = None
    user_type: UserType | None = None


class UserSelfUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    phone: Phone | None = None


class UserSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    profile_image_url: str | None
