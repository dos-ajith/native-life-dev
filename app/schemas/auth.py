from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.base import BaseReadSchema
from app.schemas.user import AuthenticatedUserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUserRead


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str = Field(pattern=r"^\d{4,8}$")


class ResendEmailVerificationRequest(BaseModel):
    email: EmailStr


class EmailVerificationResult(BaseReadSchema):
    email: EmailStr
    email_verified_at: datetime | None
