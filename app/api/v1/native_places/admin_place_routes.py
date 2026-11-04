from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import DbSessionDep, SettingsDep, SuperAdminDep
from app.api.v1.native_places.permissions import NativePlaceManageDep
from app.core.messages import NativePlaceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.native_place import NativeAdminRead, NativePlaceRead, NativePlaceUpdate
from app.schemas.response import SuccessResponse
from app.schemas.user import UserCreate
from app.services.native_admin_service import NativeAdminService
from app.services.native_place_admin_service import NativePlaceAdminService

router = APIRouter(prefix="/admin/native-places", tags=[ApiTag.ADMIN_NATIVE_PLACES])


@router.patch("/{village_id}", response_model=SuccessResponse[NativePlaceRead])
def update_native_place(
    village_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    admin: NativePlaceManageDep,
    tag_name: Annotated[str | None, Form()] = None,
    image: Annotated[UploadFile | None, File()] = None,
) -> SuccessResponse[NativePlaceRead]:
    payload = NativePlaceUpdate(tag_name=tag_name)
    village = NativePlaceAdminService(db).update(
        village_id, payload, image, settings.upload_dir, admin
    )
    return SuccessResponse(
        message=NativePlaceMessages.UPDATED, data=NativePlaceRead.from_village(village)
    )


@router.post(
    "/{village_id}/admin",
    response_model=SuccessResponse[NativeAdminRead],
    status_code=status.HTTP_201_CREATED,
)
def create_native_admin(
    village_id: UUID,
    payload: UserCreate,
    db: DbSessionDep,
    admin: SuperAdminDep,
) -> SuccessResponse[NativeAdminRead]:
    village, native_admin = NativeAdminService(db).create(village_id, payload, admin)
    return SuccessResponse(
        message=NativePlaceMessages.ADMIN_CREATED,
        data=NativeAdminRead.from_models(village, native_admin),
    )


@router.delete("/{village_id}/admin", response_model=SuccessResponse[None])
def remove_native_admin(
    village_id: UUID,
    db: DbSessionDep,
    admin: SuperAdminDep,
) -> SuccessResponse[None]:
    NativeAdminService(db).remove(village_id, admin)
    return SuccessResponse(message=NativePlaceMessages.ADMIN_REMOVED, data=None)
