from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models.auth_identity import AuthProvider
from app.schemas.auth import (
    MAX_OPAQUE_TOKEN_LENGTH,
    AuthenticatedResult,
    RegistrationRequiredResult,
)
from app.schemas.base import BaseReadSchema


class GoogleIdTokenRequest(BaseModel):
    id_token: str = Field(min_length=1, max_length=MAX_OPAQUE_TOKEN_LENGTH)


class GoogleRegistrationRequiredResult(RegistrationRequiredResult):
    email: str
    first_name: str | None
    last_name: str | None


GoogleSignInResult = Annotated[
    AuthenticatedResult | GoogleRegistrationRequiredResult, Field(discriminator="status")
]


class LinkedIdentityRead(BaseReadSchema):
    provider: AuthProvider
    email: str | None
    created_at: datetime
