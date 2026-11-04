import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AccountRoleVerificationStatus(enum.StrEnum):
    NOT_REQUIRED = "not_required"
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class SelectableAccountRoleRead(BaseModel):
    id: UUID
    name: str
    slug: str
    requires_verification: bool


class AccountRoleRead(BaseModel):
    id: UUID
    name: str
    slug: str
    requires_verification: bool
    verification_status: AccountRoleVerificationStatus
    verified_at: datetime | None
    verification_request_id: UUID | None
    selected_at: datetime | None
    selection_completed: bool


class PublicAccountRoleRead(BaseModel):
    name: str
    slug: str
    requires_verification: bool
    is_verified: bool
