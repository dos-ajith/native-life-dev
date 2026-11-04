from datetime import date, datetime
from typing import Annotated, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import User, UserGender, UserStatus, UserType
from app.schemas.account_role import AccountRoleRead, PublicAccountRoleRead
from app.schemas.base import BaseReadSchema
from app.schemas.role import RoleSummary
from app.schemas.user_follow import FollowRelationship
from app.schemas.validators import AlphanumericStr, PastDate

PHONE_PATTERN = r"^\+?[0-9]{7,15}$"

Name = Annotated[AlphanumericStr, Field(max_length=100)]
Email = Annotated[EmailStr, Field(max_length=255)]
Phone = Annotated[str, Field(max_length=30, pattern=PHONE_PATTERN)]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class UserRead(BaseReadSchema):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None
    profile_image_url: str | None
    gender: UserGender | None
    date_of_birth: date | None
    is_adult: bool | None
    status: UserStatus
    email_verified_at: datetime | None
    phone_verified_at: datetime | None
    roles: list[RoleSummary]
    account_role: AccountRoleRead | None = None

    @classmethod
    def from_user(cls, user: User, account_role: AccountRoleRead | None) -> Self:
        return cls.model_validate(user).model_copy(update={"account_role": account_role})


class UserRegistrationResult(BaseModel):
    email: EmailStr


class UserCreate(BaseModel):
    first_name: Name
    last_name: Name
    email: Email
    phone: Phone | None = None
    password: Password
    gender: UserGender | None = None
    date_of_birth: PastDate | None = None


class UserUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    email: Email | None = None
    phone: Phone | None = None
    status: UserStatus | None = None
    user_type: UserType | None = None
    gender: UserGender | None = None
    date_of_birth: PastDate | None = None


class UserSelfUpdate(BaseModel):
    first_name: Name | None = None
    last_name: Name | None = None
    gender: UserGender | None = None
    date_of_birth: PastDate | None = None


class UserDiscoveryRead(BaseModel):
    id: UUID
    name: str
    profile_image_url: str | None
    followers_count: int
    following_count: int
    is_following: bool
    follow_status: FollowRelationship


class UserProfileRead(BaseModel):
    id: UUID
    name: str
    profile_image_url: str | None
    followers_count: int
    following_count: int
    posts_count: int
    is_following: bool
    is_followed_by: bool
    follow_status: FollowRelationship
    account_role: PublicAccountRoleRead | None = None


class UserSummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    first_name: str
    last_name: str
    profile_image_url: str | None
