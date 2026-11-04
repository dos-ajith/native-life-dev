from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import EventMessages
from app.core.storage import delete_media_file, save_event_image
from app.models.event import Event
from app.models.event_image import EventImage
from app.models.user import User
from app.repositories.event_image_repository import EventImageRepository
from app.schemas.event import MAX_EVENT_IMAGES
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "event_image"


def ensure_within_image_limit(total_images: int) -> None:
    if total_images > MAX_EVENT_IMAGES:
        raise BusinessRuleError(EventMessages.TOO_MANY_IMAGES.format(limit=MAX_EVENT_IMAGES))


def ensure_captions_fit(files: list[UploadFile], captions: list[str]) -> None:
    if len(captions) > len(files):
        raise BusinessRuleError(EventMessages.TOO_MANY_CAPTIONS)


class EventImageService:
    def __init__(self, db: Session) -> None:
        self._images = EventImageRepository(db)
        self._activity_logs = ActivityLogService(db)

    def add(
        self,
        event: Event,
        files: list[UploadFile],
        captions: list[str],
        upload_dir: str,
        actor: User,
    ) -> list[EventImage]:
        ensure_captions_fit(files, captions)
        ensure_within_image_limit(self._images.count(event.id) + len(files))
        padded = [*captions, *([None] * (len(files) - len(captions)))]
        return [
            self._add_one(event, file, caption, upload_dir, actor)
            for file, caption in zip(files, padded, strict=True)
        ]

    def remove(self, event: Event, image_id: UUID, upload_dir: str, actor: User) -> None:
        image = self._images.get_in_event(event.id, image_id)
        if image is None:
            raise NotFoundError(EventMessages.IMAGE_NOT_FOUND)
        image_url = image.image_url
        self._images.delete(image)
        delete_media_file(image_url, upload_dir)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_IMAGE_REMOVED,
            entity_type=ENTITY_TYPE,
            entity_id=image.id,
            metadata={"event_id": str(event.id)},
        )

    def _add_one(
        self, event: Event, file: UploadFile, caption: str | None, upload_dir: str, actor: User
    ) -> EventImage:
        image_url = save_event_image(file, upload_dir)
        try:
            image = self._images.add(
                EventImage(
                    event_id=event.id,
                    image_url=image_url,
                    caption=caption,
                    sort_order=self._images.next_sort_order(event.id),
                )
            )
        except Exception:
            delete_media_file(image_url, upload_dir)
            raise
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_IMAGE_ADDED,
            entity_type=ENTITY_TYPE,
            entity_id=image.id,
            metadata={"event_id": str(event.id)},
        )
        return image
