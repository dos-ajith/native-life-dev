from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.api.v1.categories.permissions import (
    CategoryCreateDep,
    CategoryDeleteDep,
    CategorySuggestDep,
    CategoryUpdateDep,
)
from app.core.exceptions import BusinessRuleError
from app.core.messages import CategoryMessages
from app.core.openapi_tags import ApiTag
from app.schemas.category import CategoryCreate, CategoryRead, CategoryUpdate
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.category_service import CategoryService

router = APIRouter(prefix="/categories", tags=[ApiTag.CATEGORIES])

ROOT_PARENT_SENTINEL = "null"


def _parse_parent_id(raw: str | None) -> UUID | None:
    if raw is None or raw.strip().lower() == ROOT_PARENT_SENTINEL:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise BusinessRuleError(CategoryMessages.INVALID_PARENT_ID) from exc


@router.get("", response_model=SuccessResponse[Page[CategoryRead]])
def list_categories(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    parent_id: Annotated[str | None, Query()] = None,
    parent_slug: Annotated[str | None, Query()] = None,
    include_inactive: bool = False,
) -> SuccessResponse[Page[CategoryRead]]:
    items, total = CategoryService(db).list_by_parent(
        _parse_parent_id(parent_id),
        params,
        current_user,
        include_inactive,
        parent_slug,
    )
    page = Page[CategoryRead].create(
        items=[CategoryRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=CategoryMessages.LIST_RETRIEVED, data=page)


@router.post("", response_model=SuccessResponse[CategoryRead], status_code=status.HTTP_201_CREATED)
def create_category(
    payload: CategoryCreate, db: DbSessionDep, current_user: CategoryCreateDep
) -> SuccessResponse[CategoryRead]:
    category = CategoryService(db).create(payload, current_user)
    return SuccessResponse(
        message=CategoryMessages.CREATED, data=CategoryRead.model_validate(category)
    )


@router.post(
    "/suggest", response_model=SuccessResponse[CategoryRead], status_code=status.HTTP_201_CREATED
)
def suggest_category(
    payload: CategoryCreate, db: DbSessionDep, current_user: CategorySuggestDep
) -> SuccessResponse[CategoryRead]:
    category = CategoryService(db).suggest(payload, current_user)
    return SuccessResponse(
        message=CategoryMessages.SUGGESTED, data=CategoryRead.model_validate(category)
    )


@router.patch("/{category_id}", response_model=SuccessResponse[CategoryRead])
def update_category(
    category_id: UUID, payload: CategoryUpdate, db: DbSessionDep, current_user: CategoryUpdateDep
) -> SuccessResponse[CategoryRead]:
    category = CategoryService(db).update(category_id, payload, current_user)
    return SuccessResponse(
        message=CategoryMessages.UPDATED, data=CategoryRead.model_validate(category)
    )


@router.delete("/{category_id}", response_model=SuccessResponse[None])
def delete_category(
    category_id: UUID, db: DbSessionDep, current_user: CategoryDeleteDep
) -> SuccessResponse[None]:
    CategoryService(db).delete(category_id, current_user)
    return SuccessResponse(message=CategoryMessages.DELETED, data=None)
