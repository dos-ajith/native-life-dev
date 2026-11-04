from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.lost_found.permissions import (
    LostFoundCreateDep,
    LostFoundDeleteDep,
    LostFoundManageDep,
    LostFoundViewDep,
)
from app.core.messages import LostFoundMessages
from app.core.openapi_tags import ApiTag
from app.models.lost_found_item import LostFoundKind
from app.schemas.lost_found import (
    LostFoundCreate,
    LostFoundListQuery,
    LostFoundRead,
    LostFoundResponseCreate,
    LostFoundUpdate,
)
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.lost_found_service import LostFoundService

router = APIRouter(prefix="/lost-found", tags=[ApiTag.LOST_FOUND])


@router.post("", response_model=SuccessResponse[LostFoundRead], status_code=status.HTTP_201_CREATED)
def create_report(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: LostFoundCreateDep,
    kind: Annotated[LostFoundKind, Form()],
    category_id: Annotated[UUID, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    location_name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
    occurred_on: Annotated[date, Form()],
    contact_info: Annotated[str, Form()],
    images: Annotated[list[UploadFile] | None, File()] = None,
) -> SuccessResponse[LostFoundRead]:
    payload = LostFoundCreate(
        kind=kind,
        category_id=category_id,
        title=title,
        description=description,
        location_name=location_name,
        latitude=latitude,
        longitude=longitude,
        occurred_on=occurred_on,
        contact_info=contact_info,
    )
    report = LostFoundService(db).create(payload, images or [], settings.upload_dir, current_user)
    return SuccessResponse(message=LostFoundMessages.CREATED, data=report)


@router.get("", response_model=SuccessResponse[Page[LostFoundRead]])
def list_reports(
    db: DbSessionDep,
    viewer: LostFoundViewDep,
    params: PaginationDep,
    query: Annotated[LostFoundListQuery, Query()],
) -> SuccessResponse[Page[LostFoundRead]]:
    items, total = LostFoundService(db).list_for(params, viewer, query)
    return SuccessResponse(
        message=LostFoundMessages.LIST_RETRIEVED,
        data=Page[LostFoundRead].create(items=items, total=total, params=params),
    )


@router.get("/{item_id}", response_model=SuccessResponse[LostFoundRead])
def get_report(
    item_id: UUID, db: DbSessionDep, viewer: LostFoundViewDep
) -> SuccessResponse[LostFoundRead]:
    return SuccessResponse(
        message=LostFoundMessages.RETRIEVED, data=LostFoundService(db).get_read(item_id, viewer)
    )


@router.patch("/{item_id}", response_model=SuccessResponse[LostFoundRead])
def update_report(
    item_id: UUID, payload: LostFoundUpdate, db: DbSessionDep, current_user: LostFoundManageDep
) -> SuccessResponse[LostFoundRead]:
    report = LostFoundService(db).update(item_id, payload, current_user)
    return SuccessResponse(message=LostFoundMessages.UPDATED, data=report)


@router.post("/{item_id}/resolve", response_model=SuccessResponse[LostFoundRead])
def resolve_report(
    item_id: UUID, db: DbSessionDep, current_user: LostFoundManageDep
) -> SuccessResponse[LostFoundRead]:
    report = LostFoundService(db).resolve(item_id, current_user)
    return SuccessResponse(message=LostFoundMessages.RESOLVED, data=report)


@router.post("/{item_id}/respond", response_model=SuccessResponse[None])
def respond_to_report(
    item_id: UUID,
    payload: LostFoundResponseCreate,
    db: DbSessionDep,
    current_user: LostFoundViewDep,
) -> SuccessResponse[None]:
    LostFoundService(db).respond(item_id, payload, current_user)
    return SuccessResponse(message=LostFoundMessages.RESPONDED, data=None)


@router.delete("/{item_id}", response_model=SuccessResponse[None])
def delete_report(
    item_id: UUID, db: DbSessionDep, current_user: LostFoundDeleteDep
) -> SuccessResponse[None]:
    LostFoundService(db).delete(item_id, current_user)
    return SuccessResponse(message=LostFoundMessages.DELETED, data=None)
