from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.categories.permissions import (
    CategoryApproveDep,
    CategoryRejectDep,
    CategoryViewPendingDep,
)
from app.core.messages import CategoryMessages
from app.core.openapi_tags import ApiTag
from app.schemas.category import CategoryReject, CategorySubmissionRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.category_service import CategoryService

router = APIRouter(prefix="/admin/categories", tags=[ApiTag.ADMIN_CATEGORY_REVIEW])


@router.get("/pending", response_model=SuccessResponse[Page[CategorySubmissionRead]])
def list_pending_categories(
    db: DbSessionDep, _: CategoryViewPendingDep, params: PaginationDep
) -> SuccessResponse[Page[CategorySubmissionRead]]:
    items, total = CategoryService(db).list_pending(params)
    page = Page[CategorySubmissionRead].create(
        items=[CategorySubmissionRead.from_category(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=CategoryMessages.PENDING_LIST_RETRIEVED, data=page)


@router.post("/{category_id}/approve", response_model=SuccessResponse[CategorySubmissionRead])
def approve_category(
    category_id: UUID, db: DbSessionDep, admin: CategoryApproveDep
) -> SuccessResponse[CategorySubmissionRead]:
    category = CategoryService(db).approve(category_id, admin)
    return SuccessResponse(
        message=CategoryMessages.APPROVED, data=CategorySubmissionRead.from_category(category)
    )


@router.post("/{category_id}/reject", response_model=SuccessResponse[CategorySubmissionRead])
def reject_category(
    category_id: UUID, payload: CategoryReject, db: DbSessionDep, admin: CategoryRejectDep
) -> SuccessResponse[CategorySubmissionRead]:
    category = CategoryService(db).reject(category_id, admin, payload.review_note)
    return SuccessResponse(
        message=CategoryMessages.REJECTED, data=CategorySubmissionRead.from_category(category)
    )
