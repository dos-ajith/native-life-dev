from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, UploadFile, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import BusinessMessages
from app.core.openapi_tags import ApiTag
from app.schemas.business import BusinessImageRead
from app.schemas.response import SuccessResponse
from app.services.business_image_service import BusinessImageService

router = APIRouter(prefix="/businesses/{business_id}/images", tags=[ApiTag.BUSINESS_IMAGES])


@router.post(
    "", response_model=SuccessResponse[BusinessImageRead], status_code=status.HTTP_201_CREATED
)
def add_business_image(
    business_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
    file: Annotated[UploadFile, File()],
) -> SuccessResponse[BusinessImageRead]:
    image = BusinessImageService(db).add(business_id, file, settings.upload_dir, current_user)
    return SuccessResponse(
        message=BusinessMessages.IMAGE_ADDED, data=BusinessImageRead.model_validate(image)
    )


@router.get("", response_model=SuccessResponse[list[BusinessImageRead]])
def list_business_images(
    business_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[BusinessImageRead]]:
    images = BusinessImageService(db).list_for_viewer(business_id, current_user)
    return SuccessResponse(
        message=BusinessMessages.IMAGES_RETRIEVED,
        data=[BusinessImageRead.model_validate(image) for image in images],
    )


@router.delete("/{image_id}", response_model=SuccessResponse[None])
def delete_business_image(
    business_id: UUID,
    image_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[None]:
    BusinessImageService(db).delete(business_id, image_id, settings.upload_dir, current_user)
    return SuccessResponse(message=BusinessMessages.IMAGE_DELETED, data=None)
