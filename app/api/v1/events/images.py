from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import DbSessionDep, SettingsDep
from app.api.v1.events.permissions import EventManageDep
from app.core.messages import EventMessages
from app.core.openapi_tags import ApiTag
from app.schemas.event import EventRead
from app.schemas.response import SuccessResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events/{event_id}/images", tags=[ApiTag.EVENTS])


@router.post("", response_model=SuccessResponse[EventRead], status_code=status.HTTP_201_CREATED)
def add_event_images(
    event_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: EventManageDep,
    images: Annotated[list[UploadFile], File()],
    captions: Annotated[list[str] | None, Form()] = None,
) -> SuccessResponse[EventRead]:
    event = EventService(db).add_images(
        event_id, images, captions or [], settings.upload_dir, current_user
    )
    return SuccessResponse(message=EventMessages.IMAGE_ADDED, data=event)


@router.delete("/{image_id}", response_model=SuccessResponse[None])
def delete_event_image(
    event_id: UUID,
    image_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: EventManageDep,
) -> SuccessResponse[None]:
    EventService(db).remove_image(event_id, image_id, settings.upload_dir, current_user)
    return SuccessResponse(message=EventMessages.IMAGE_DELETED, data=None)
