from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import LostFoundMessages
from app.core.storage import delete_media_file, save_lost_found_image
from app.models.lost_found_image import LostFoundImage
from app.models.lost_found_item import LostFoundItem
from app.models.user import User
from app.repositories.lost_found_image_repository import LostFoundImageRepository
from app.schemas.lost_found import MAX_LOST_FOUND_IMAGES
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "lost_found_image"


def ensure_within_image_limit(total_images: int) -> None:
    if total_images > MAX_LOST_FOUND_IMAGES:
        raise BusinessRuleError(
            LostFoundMessages.TOO_MANY_IMAGES.format(limit=MAX_LOST_FOUND_IMAGES)
        )


class LostFoundImageService:
    def __init__(self, db: Session) -> None:
        self._images = LostFoundImageRepository(db)
        self._activity_logs = ActivityLogService(db)

    def add(
        self, item: LostFoundItem, files: list[UploadFile], upload_dir: str, actor: User
    ) -> list[LostFoundImage]:
        ensure_within_image_limit(self._images.count(item.id) + len(files))
        return [self._add_one(item, file, upload_dir, actor) for file in files]

    def remove(self, item: LostFoundItem, image_id: UUID, upload_dir: str, actor: User) -> None:
        image = self._images.get_in_item(item.id, image_id)
        if image is None:
            raise NotFoundError(LostFoundMessages.IMAGE_NOT_FOUND)
        image_url = image.image_url
        self._images.delete(image)
        delete_media_file(image_url, upload_dir)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_IMAGE_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=image.id,
            metadata={"item_id": str(item.id)},
        )

    def _add_one(
        self, item: LostFoundItem, file: UploadFile, upload_dir: str, actor: User
    ) -> LostFoundImage:
        image_url = save_lost_found_image(file, upload_dir)
        try:
            image = self._images.add(
                LostFoundImage(
                    item_id=item.id,
                    image_url=image_url,
                    sort_order=self._images.next_sort_order(item.id),
                )
            )
        except Exception:
            delete_media_file(image_url, upload_dir)
            raise
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.LOST_FOUND_IMAGE_ADDED,
            entity_type=ENTITY_TYPE,
            entity_id=image.id,
            metadata={"item_id": str(item.id)},
        )
        return image
