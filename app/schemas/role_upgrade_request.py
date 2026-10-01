from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.role_upgrade_request import RoleUpgradeRequestStatus
from app.schemas.base import BaseReadSchema
from app.schemas.role import RoleSummary
from app.schemas.user import UserSummaryRead


class RoleUpgradeRequestDocumentRead(BaseReadSchema):
    id: UUID
    file_name: str
    content_type: str
    file_size_bytes: int
    created_at: datetime


class RoleUpgradeRequestRead(BaseReadSchema):
    id: UUID
    user_id: UUID
    user: UserSummaryRead
    requested_role: RoleSummary
    status: RoleUpgradeRequestStatus
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    documents: list[RoleUpgradeRequestDocumentRead]


class RoleUpgradeRequestCreate(BaseModel):
    requested_role_id: UUID


class RoleUpgradeRequestReject(BaseModel):
    review_note: Annotated[str, Field(min_length=1, max_length=1000)]
