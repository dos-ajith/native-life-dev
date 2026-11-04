from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.category import Category, CategoryStatus
from app.schemas.base import BaseReadSchema
from app.schemas.user import UserSummaryRead
from app.schemas.validators import NonBlankStr

CategoryName = Annotated[NonBlankStr, Field(max_length=100)]
MAX_CATEGORY_SORT_ORDER = 1_000_000
CategorySortOrder = Annotated[int, Field(ge=0, le=MAX_CATEGORY_SORT_ORDER)]
CategoryDescription = Annotated[NonBlankStr, Field(max_length=500)]
ReviewNote = Annotated[NonBlankStr, Field(max_length=1000)]


class CategoryCreate(BaseModel):
    name: CategoryName
    description: CategoryDescription | None = None
    parent_id: UUID | None = None


class CategoryUpdate(BaseModel):
    name: CategoryName | None = None
    description: CategoryDescription | None = None
    parent_id: UUID | None = None
    is_active: bool | None = None
    sort_order: CategorySortOrder | None = None


class CategoryReject(BaseModel):
    review_note: ReviewNote


class CategoryRead(BaseReadSchema):
    id: UUID
    parent_id: UUID | None
    name: str
    slug: str
    description: str | None
    is_active: bool
    sort_order: int
    status: CategoryStatus
    created_at: datetime
    updated_at: datetime


class CategoryRef(BaseModel):
    id: UUID
    name: str


class CategoryWithParentRead(BaseModel):
    id: UUID
    name: str
    parent: CategoryRef | None


class CategorySubmissionRead(BaseReadSchema):
    id: UUID
    name: str
    description: str | None
    status: CategoryStatus
    parent: CategoryRef | None
    submitter: UserSummaryRead | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime

    @classmethod
    def from_category(cls, category: Category) -> "CategorySubmissionRead":
        parent = category.parent
        submitter = category.submitter
        return cls(
            id=category.id,
            name=category.name,
            description=category.description,
            status=category.status,
            parent=CategoryRef(id=parent.id, name=parent.name) if parent else None,
            submitter=UserSummaryRead.model_validate(submitter) if submitter else None,
            reviewed_at=category.reviewed_at,
            review_note=category.review_note,
            created_at=category.created_at,
        )
