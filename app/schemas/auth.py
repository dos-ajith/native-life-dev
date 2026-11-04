from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.models.user import User, UserGender, UserStatus
from app.schemas.account_role import AccountRoleRead
from app.schemas.base import BaseReadSchema
from app.schemas.native_place import UserNativePlaceRead
from app.schemas.role import RoleWithPermissions
from app.schemas.user import Email, Name
from app.schemas.validators import AcceptedBool, PastDate

MAX_OPAQUE_TOKEN_LENGTH = 2048


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthenticatedUserRead(BaseReadSchema):
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
    linked_providers: list[str]
    roles: list[RoleWithPermissions] = Field(validation_alias="approved_roles")
    account_role: AccountRoleRead | None = None
    has_aadhaar_document: bool = False
    native_places: list[UserNativePlaceRead] = []

    @classmethod
    def from_user(
        cls,
        user: User,
        account_role: AccountRoleRead | None,
        has_aadhaar_document: bool,
        native_places: list[UserNativePlaceRead],
    ) -> Self:
        return cls.model_validate(user).model_copy(
            update={
                "account_role": account_role,
                "has_aadhaar_document": has_aadhaar_document,
                "native_places": native_places,
            }
        )


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    access_token_expires_at: datetime
    user: AuthenticatedUserRead


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=MAX_OPAQUE_TOKEN_LENGTH)


class AuthenticatedResult(TokenResponse):
    status: Literal["authenticated"] = "authenticated"


class RegistrationRequiredResult(BaseModel):
    status: Literal["registration_required"] = "registration_required"
    registration_token: str
    registration_token_expires_in_seconds: int


class CompleteRegistrationRequest(BaseModel):
    registration_token: str = Field(min_length=1, max_length=MAX_OPAQUE_TOKEN_LENGTH)
    first_name: Name
    last_name: Name
    accept_terms: AcceptedBool
    gender: UserGender | None = None
    date_of_birth: PastDate | None = None


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{4,8}$")


class LinkEmailRequest(BaseModel):
    email: Email


class ResendEmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationResult(BaseReadSchema):
    email: EmailStr
    email_verified_at: datetime | None
