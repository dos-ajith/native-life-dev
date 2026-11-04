from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.popular_places.permissions import PopularPlaceManageDep
from app.core.messages import PopularPlaceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.pagination import Page
from app.schemas.popular_place import (
    PopularPlaceAdminRead,
    PopularPlaceCreate,
    PopularPlaceUpdate,
)
from app.schemas.response import SuccessResponse
from app.services.popular_place_service import PopularPlaceService

router = APIRouter(prefix="/admin/popular-places", tags=[ApiTag.ADMIN_POPULAR_PLACES])


@router.get("", response_model=SuccessResponse[Page[PopularPlaceAdminRead]])
def list_popular_places(
    db: DbSessionDep,
    _: PopularPlaceManageDep,
    params: PaginationDep,
    district_id: UUID | None = None,
) -> SuccessResponse[Page[PopularPlaceAdminRead]]:
    items, total = PopularPlaceService(db).list_all(district_id, params)
    page = Page[PopularPlaceAdminRead].create(
        items=[PopularPlaceAdminRead.from_popular_place(item) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=PopularPlaceMessages.LIST_RETRIEVED, data=page)


@router.get("/{popular_place_id}", response_model=SuccessResponse[PopularPlaceAdminRead])
def get_popular_place(
    popular_place_id: UUID, db: DbSessionDep, _: PopularPlaceManageDep
) -> SuccessResponse[PopularPlaceAdminRead]:
    popular_place = PopularPlaceService(db).get(popular_place_id)
    return SuccessResponse(
        message=PopularPlaceMessages.RETRIEVED,
        data=PopularPlaceAdminRead.from_popular_place(popular_place),
    )


@router.post(
    "",
    response_model=SuccessResponse[PopularPlaceAdminRead],
    status_code=status.HTTP_201_CREATED,
)
def create_popular_place(
    db: DbSessionDep,
    settings: SettingsDep,
    admin: PopularPlaceManageDep,
    village_id: Annotated[UUID, Form()],
    image: Annotated[UploadFile, File()],
    sort_order: Annotated[int, Form()] = 0,
    is_active: Annotated[bool, Form()] = True,
) -> SuccessResponse[PopularPlaceAdminRead]:
    payload = PopularPlaceCreate(village_id=village_id, sort_order=sort_order, is_active=is_active)
    popular_place = PopularPlaceService(db).create(payload, image, settings.upload_dir, admin)
    return SuccessResponse(
        message=PopularPlaceMessages.CREATED,
        data=PopularPlaceAdminRead.from_popular_place(popular_place),
    )


@router.patch("/{popular_place_id}", response_model=SuccessResponse[PopularPlaceAdminRead])
def update_popular_place(
    popular_place_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    admin: PopularPlaceManageDep,
    village_id: Annotated[UUID | None, Form()] = None,
    sort_order: Annotated[int | None, Form()] = None,
    is_active: Annotated[bool | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[PopularPlaceAdminRead]:
    provided = {"village_id": village_id, "sort_order": sort_order, "is_active": is_active}
    payload = PopularPlaceUpdate(
        **{key: value for key, value in provided.items() if value is not None}
    )
    popular_place = PopularPlaceService(db).update(
        popular_place_id, payload, image, settings.upload_dir, admin
    )
    return SuccessResponse(
        message=PopularPlaceMessages.UPDATED,
        data=PopularPlaceAdminRead.from_popular_place(popular_place),
    )


@router.delete("/{popular_place_id}", response_model=SuccessResponse[None])
def delete_popular_place(
    popular_place_id: UUID, db: DbSessionDep, settings: SettingsDep, admin: PopularPlaceManageDep
) -> SuccessResponse[None]:
    PopularPlaceService(db).delete(popular_place_id, settings.upload_dir, admin)
    return SuccessResponse(message=PopularPlaceMessages.DELETED, data=None)
