from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import (
    ActivityRequestMetaDep,
    CurrentActiveUserDep,
    DbSessionDep,
    PaginationDep,
    SettingsDep,
)
from app.api.v1.businesses.permissions import BusinessSearchDep
from app.core.messages import BusinessMessages
from app.core.openapi_tags import ApiTag
from app.schemas.business import (
    BusinessCreate,
    BusinessCreatedRead,
    BusinessDetailRead,
    BusinessDiscoveryQuery,
    BusinessRead,
    BusinessSummaryRead,
    BusinessUpdate,
)
from app.schemas.category import CategoryRead
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.business_attachment_storage import BusinessUploads
from app.services.business_category_service import BusinessCategoryService
from app.services.business_image_service import BusinessImageService
from app.services.business_service import BusinessService

router = APIRouter(prefix="/businesses", tags=[ApiTag.BUSINESSES])
me_router = APIRouter(prefix="/me/businesses", tags=[ApiTag.BUSINESSES])


@router.post(
    "", response_model=SuccessResponse[BusinessCreatedRead], status_code=status.HTTP_201_CREATED
)
def create_business(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
    name: Annotated[str, Form()],
    category_id: Annotated[UUID, Form()],
    description: Annotated[str | None, Form()] = None,
    latitude: Annotated[float | None, Form()] = None,
    longitude: Annotated[float | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    documents: Annotated[list[UploadFile] | None, File()] = None,
    document_types: Annotated[list[str] | None, Form()] = None,
) -> SuccessResponse[BusinessCreatedRead]:
    payload = BusinessCreate(
        name=name,
        category_id=category_id,
        description=description,
        latitude=latitude,
        longitude=longitude,
        document_types=document_types or [],
    )
    uploads = BusinessUploads(
        images=images or [],
        documents=documents or [],
        upload_dir=settings.upload_dir,
        private_upload_dir=settings.private_upload_dir,
    )
    created = BusinessService(db).create(
        payload, uploads, current_user, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessMessages.CREATED,
        data=BusinessCreatedRead.from_created(created.business, created.images, created.documents),
    )


@router.get("/categories", response_model=SuccessResponse[Page[CategoryRead]])
def list_business_categories(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    params: PaginationDep,
    parent_id: UUID | None = None,
) -> SuccessResponse[Page[CategoryRead]]:
    items, total = BusinessCategoryService(db).list_children(parent_id, params, current_user)
    page = Page[CategoryRead].create(
        items=[CategoryRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=BusinessMessages.CATEGORIES_RETRIEVED, data=page)


@router.get("", response_model=SuccessResponse[Page[BusinessSummaryRead]])
def search_businesses(
    db: DbSessionDep,
    current_user: BusinessSearchDep,
    params: PaginationDep,
    query: Annotated[BusinessDiscoveryQuery, Query()],
) -> SuccessResponse[Page[BusinessSummaryRead]]:
    items, total = BusinessService(db).search_nearby(query, params, current_user)
    page = Page[BusinessSummaryRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=BusinessMessages.LIST_RETRIEVED, data=page)


@router.get("/{business_id}", response_model=SuccessResponse[BusinessDetailRead])
def get_business(
    business_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[BusinessDetailRead]:
    business = BusinessService(db).get_for_actor(business_id, current_user)
    images = BusinessImageService(db).list_for_business(business)
    return SuccessResponse(
        message=BusinessMessages.RETRIEVED,
        data=BusinessDetailRead.from_business_with_images(business, images),
    )


@router.patch("/{business_id}", response_model=SuccessResponse[BusinessRead])
def update_business(
    business_id: UUID,
    payload: BusinessUpdate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[BusinessRead]:
    business = BusinessService(db).update(
        business_id, payload, current_user, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessMessages.UPDATED, data=BusinessRead.from_business(business)
    )


@router.post("/{business_id}/resubmit", response_model=SuccessResponse[BusinessRead])
def resubmit_business(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[BusinessRead]:
    business = BusinessService(db).resubmit(
        business_id, current_user, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessMessages.RESUBMITTED, data=BusinessRead.from_business(business)
    )


@router.delete("/{business_id}", response_model=SuccessResponse[None])
def delete_business(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[None]:
    BusinessService(db).delete(business_id, current_user, meta.ip_address, meta.user_agent)
    return SuccessResponse(message=BusinessMessages.DELETED, data=None)


@me_router.get("", response_model=SuccessResponse[Page[BusinessRead]])
def list_my_businesses(
    db: DbSessionDep, current_user: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[BusinessRead]]:
    items, total = BusinessService(db).list_own(current_user, params)
    page = Page[BusinessRead].create(
        items=[BusinessRead.from_business(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=BusinessMessages.LIST_RETRIEVED, data=page)
