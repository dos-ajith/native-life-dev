from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status

from app.api.deps import (
    DbSessionDep,
    PaginationDep,
    ProfileImageDep,
    SettingsDep,
    require_permission,
)
from app.core.messages import PageMessages
from app.core.permissions import PermissionName
from app.models.page import PageStatus
from app.models.user import User
from app.schemas.page import PageCreate, PageRead, PageUpdate
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.page_service import PageService

router = APIRouter(prefix="/admin/pages", tags=["pages"])

PageCreateDep = Annotated[User, Depends(require_permission(PermissionName.PAGE_CREATE))]
PageViewDep = Annotated[User, Depends(require_permission(PermissionName.PAGE_VIEW))]
PageUpdateDep = Annotated[User, Depends(require_permission(PermissionName.PAGE_UPDATE))]
PageDeleteDep = Annotated[User, Depends(require_permission(PermissionName.PAGE_DELETE))]


@router.post(
    "/create", response_model=SuccessResponse[PageRead], status_code=status.HTTP_201_CREATED
)
def create_page(
    db: DbSessionDep,
    current_user: PageCreateDep,
    settings: SettingsDep,
    title: Annotated[str, Form()],
    content: Annotated[str | None, Form()] = None,
    page_status: Annotated[PageStatus, Form(alias="status")] = PageStatus.DRAFT,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[PageRead]:
    payload = PageCreate(title=title, content=content, status=page_status)
    page = PageService(db).create(payload, current_user)
    if image is not None:
        page = PageService(db).update_image(page.id, image, settings.upload_dir)
    return SuccessResponse(message=PageMessages.CREATED, data=PageRead.model_validate(page))


@router.get("", response_model=SuccessResponse[Page[PageRead]])
def list_pages(
    db: DbSessionDep, _: PageViewDep, params: PaginationDep
) -> SuccessResponse[Page[PageRead]]:
    items, total = PageService(db).list(params)
    page = Page[PageRead].create(
        items=[PageRead.model_validate(item) for item in items], total=total, params=params
    )
    return SuccessResponse(message=PageMessages.LIST_RETRIEVED, data=page)


@router.get("/edit/{page_id}", response_model=SuccessResponse[PageRead])
def edit_page(page_id: UUID, db: DbSessionDep, _: PageViewDep) -> SuccessResponse[PageRead]:
    page = PageService(db).get(page_id)
    return SuccessResponse(message=PageMessages.RETRIEVED, data=PageRead.model_validate(page))


@router.get("/slug/{slug}", response_model=SuccessResponse[PageRead])
def get_page_by_slug(
    slug: str, db: DbSessionDep, _: PageViewDep
) -> SuccessResponse[PageRead]:
    page = PageService(db).get_by_slug(slug)
    return SuccessResponse(message=PageMessages.RETRIEVED, data=PageRead.model_validate(page))


@router.patch("/update/{page_id}", response_model=SuccessResponse[PageRead])
def update_page(
    page_id: UUID,
    db: DbSessionDep,
    current_user: PageUpdateDep,
    settings: SettingsDep,
    title: Annotated[str | None, Form()] = None,
    content: Annotated[str | None, Form()] = None,
    page_status: Annotated[PageStatus | None, Form(alias="status")] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[PageRead]:
    payload = PageUpdate(title=title, content=content, status=page_status)
    page = PageService(db).update(page_id, payload, current_user)
    if image is not None:
        page = PageService(db).update_image(page_id, image, settings.upload_dir)
    return SuccessResponse(message=PageMessages.UPDATED, data=PageRead.model_validate(page))


@router.delete("/delete/{page_id}", response_model=SuccessResponse[None])
def delete_page(page_id: UUID, db: DbSessionDep, _: PageDeleteDep) -> SuccessResponse[None]:
    PageService(db).delete(page_id)
    return SuccessResponse(message=PageMessages.DELETED, data=None)


@router.post("/update/{page_id}/image", response_model=SuccessResponse[PageRead])
def update_page_image(
    page_id: UUID,
    db: DbSessionDep,
    _: PageUpdateDep,
    settings: SettingsDep,
    image: ProfileImageDep,
) -> SuccessResponse[PageRead]:
    page = PageService(db).update_image(page_id, image, settings.upload_dir)
    return SuccessResponse(message=PageMessages.IMAGE_UPDATED, data=PageRead.model_validate(page))
