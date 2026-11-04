from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import DealMessages
from app.core.openapi_tags import ApiTag
from app.schemas.deal import DealRead
from app.schemas.response import SuccessResponse
from app.services.deal_image_service import DealImageService

router = APIRouter(prefix="/deals/{deal_id}/images", tags=[ApiTag.DEAL_IMAGES])

PRIVATE_IMAGE_CACHE_CONTROL = "private, no-cache"


@router.post("", response_model=SuccessResponse[DealRead], status_code=status.HTTP_201_CREATED)
def add_deal_image(
    deal_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    file: Annotated[UploadFile, File()],
    is_thumbnail: Annotated[bool, Form()] = False,
) -> SuccessResponse[DealRead]:
    deal = DealImageService(db).add(
        deal_id, file, is_thumbnail, settings.private_upload_dir, current_user
    )
    return SuccessResponse(message=DealMessages.IMAGE_ADDED, data=deal)


@router.post("/{image_id}/thumbnail", response_model=SuccessResponse[DealRead])
def set_deal_thumbnail(
    deal_id: UUID, image_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealImageService(db).set_thumbnail(deal_id, image_id, current_user)
    return SuccessResponse(message=DealMessages.THUMBNAIL_SET, data=deal)


@router.delete("/{image_id}", response_model=SuccessResponse[DealRead])
def delete_deal_image(
    deal_id: UUID, image_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DealRead]:
    deal = DealImageService(db).remove(deal_id, image_id, current_user)
    return SuccessResponse(message=DealMessages.IMAGE_DELETED, data=deal)


@router.get("/{image_id}/file")
def get_deal_image_file(
    deal_id: UUID, image_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> FileResponse:
    image = DealImageService(db).get_viewable(deal_id, image_id, current_user)
    return FileResponse(
        path=image.storage_path,
        media_type=image.content_type,
        filename=Path(image.storage_path).name,
        content_disposition_type="inline",
        headers={"Cache-Control": PRIVATE_IMAGE_CACHE_CONTROL},
    )
