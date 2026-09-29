from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.role_upgrade_request import RoleUpgradeRequestStatus
from app.schemas.role import RoleSummary

ReviewNote = Annotated[str, Field(max_length=1000)]


class RoleUpgradeRequestDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_name: str
    content_type: str
    file_size_bytes: int
    created_at: datetime


class RoleUpgradeRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    requested_role: RoleSummary
    status: RoleUpgradeRequestStatus
    reason: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    documents: list[RoleUpgradeRequestDocumentRead]


class RoleUpgradeRequestCreate(BaseModel):
    requested_role_id: UUID
    reason: ReviewNote | None = None


class RoleUpgradeRequestReject(BaseModel):
    review_note: Annotated[str, Field(min_length=1, max_length=1000)]
