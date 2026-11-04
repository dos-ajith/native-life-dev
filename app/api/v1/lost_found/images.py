from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import DbSessionDep, SettingsDep
from app.api.v1.lost_found.permissions import LostFoundManageDep
from app.core.messages import LostFoundMessages
from app.core.openapi_tags import ApiTag
from app.schemas.lost_found import LostFoundRead
from app.schemas.response import SuccessResponse
from app.services.lost_found_service import LostFoundService

router = APIRouter(prefix="/lost-found/{item_id}/images", tags=[ApiTag.LOST_FOUND])


@router.post("", response_model=SuccessResponse[LostFoundRead], status_code=status.HTTP_201_CREATED)
def add_report_images(
    item_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: LostFoundManageDep,
    images: Annotated[list[UploadFile], File()],
) -> SuccessResponse[LostFoundRead]:
    report = LostFoundService(db).add_images(item_id, images, settings.upload_dir, current_user)
    return SuccessResponse(message=LostFoundMessages.IMAGE_ADDED, data=report)


@router.delete("/{image_id}", response_model=SuccessResponse[None])
def delete_report_image(
    item_id: UUID,
    image_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: LostFoundManageDep,
) -> SuccessResponse[None]:
    LostFoundService(db).remove_image(item_id, image_id, settings.upload_dir, current_user)
    return SuccessResponse(message=LostFoundMessages.IMAGE_DELETED, data=None)
