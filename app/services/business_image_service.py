from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import NotFoundError
from app.core.messages import BusinessMessages
from app.core.permissions import PermissionName
from app.core.storage import delete_media_file, save_business_image
from app.models.business import Business, BusinessStatus
from app.models.business_image import BusinessImage
from app.models.user import User
from app.repositories.business_image_repository import BusinessImageRepository
from app.services.activity_log_service import ActivityLogService
from app.services.business_service import BusinessService

ENTITY_TYPE = "business_image"


class BusinessImageService:
    def __init__(self, db: Session) -> None:
        self._images = BusinessImageRepository(db)
        self._businesses = BusinessService(db)
        self._activity_logs = ActivityLogService(db)

    def add(
        self, business_id: UUID, file: UploadFile, upload_dir: str, actor: User
    ) -> BusinessImage:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        image_url = save_business_image(file, upload_dir)
        try:
            image = self._images.add(
                BusinessImage(
                    business_id=business.id,
                    image_url=image_url,
                    sort_order=self._images.next_sort_order(business.id),
                )
            )
        except Exception:
            delete_media_file(image_url, upload_dir)
            raise
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_IMAGE_ADDED,
            entity_type=ENTITY_TYPE,
            entity_id=image.id,
            metadata={"business_id": str(business.id)},
        )
        return image

    def list_for_viewer(self, business_id: UUID, viewer: User) -> list[BusinessImage]:
        business = self._businesses.get(business_id)
        if business.status != BusinessStatus.ACTIVE:
            business = self._businesses.get_for_actor(business_id, viewer)
        return self._images.list_by_business(business.id)

    def list_for_business(self, business: Business) -> list[BusinessImage]:
        return self._images.list_by_business(business.id)

    def delete(self, business_id: UUID, image_id: UUID, upload_dir: str, actor: User) -> None:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        image = self._images.get_by_id(image_id)
        if image is None or image.business_id != business.id:
            raise NotFoundError(BusinessMessages.IMAGE_NOT_FOUND)
        image_url = image.image_url
        self._images.delete(image)
        delete_media_file(image_url, upload_dir)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.BUSINESS_IMAGE_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=image_id,
            metadata={"business_id": str(business.id)},
        )
