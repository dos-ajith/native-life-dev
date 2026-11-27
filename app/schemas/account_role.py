import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.config import get_settings


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


class DocumentVerificationStatus(enum.StrEnum):
    NOT_REQUIRED = "not_required"
    DOCUMENT_REQUIRED = "document_required"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


def verification_document_file_url(request_id: UUID, document_id: UUID) -> str:
    return f"{get_settings().api_v1_prefix}/upgrade-requests/{request_id}/documents/{document_id}"


class VerificationDocumentRead(BaseModel):
    id: UUID
    request_id: UUID
    file_name: str
    content_type: str
    file_size_bytes: int
    file_url: str
    uploaded_at: datetime


class VerificationRoleRead(BaseModel):
    id: UUID
    name: str
    slug: str


class AccountRoleVerificationRead(BaseModel):
    role: VerificationRoleRead | None
    status: DocumentVerificationStatus
    is_verified: bool
    request_id: UUID | None
    review_note: str | None
    document: VerificationDocumentRead | None
