from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile, status

from app.api.deps import DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.events.permissions import (
    EventCreateDep,
    EventDeleteDep,
    EventFeatureDep,
    EventManageDep,
    EventViewDep,
)
from app.core.messages import EventMessages
from app.core.openapi_tags import ApiTag
from app.schemas.event import EventCreate, EventListQuery, EventRead, EventUpdate
from app.schemas.pagination import Page
from app.schemas.response import SuccessResponse
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=[ApiTag.EVENTS])


@router.post("", response_model=SuccessResponse[EventRead], status_code=status.HTTP_201_CREATED)
def create_event(
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: EventCreateDep,
    category_id: Annotated[UUID, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    venue_name: Annotated[str, Form()],
    latitude: Annotated[float, Form()],
    longitude: Annotated[float, Form()],
    starts_at: Annotated[datetime, Form()],
    ends_at: Annotated[datetime, Form()],
    organizer_name: Annotated[str | None, Form()] = None,
    organizer_phone: Annotated[str | None, Form()] = None,
    images: Annotated[list[UploadFile] | None, File()] = None,
    captions: Annotated[list[str] | None, Form()] = None,
) -> SuccessResponse[EventRead]:
    payload = EventCreate(
        category_id=category_id,
        title=title,
        description=description,
        venue_name=venue_name,
        latitude=latitude,
        longitude=longitude,
        starts_at=starts_at,
        ends_at=ends_at,
        organizer_name=organizer_name,
        organizer_phone=organizer_phone,
    )
    event = EventService(db).create(
        payload, images or [], captions or [], settings.upload_dir, current_user
    )
    return SuccessResponse(message=EventMessages.CREATED, data=event)


@router.get("", response_model=SuccessResponse[Page[EventRead]])
def list_events(
    db: DbSessionDep,
    viewer: EventViewDep,
    params: PaginationDep,
    query: Annotated[EventListQuery, Query()],
) -> SuccessResponse[Page[EventRead]]:
    events, total = EventService(db).list_for(params, viewer, query)
    return SuccessResponse(
        message=EventMessages.LIST_RETRIEVED,
        data=Page[EventRead].create(items=events, total=total, params=params),
    )


@router.get("/featured", response_model=SuccessResponse[EventRead | None])
def get_featured_event(
    db: DbSessionDep, viewer: EventViewDep, query: Annotated[EventListQuery, Query()]
) -> SuccessResponse[EventRead | None]:
    return SuccessResponse(
        message=EventMessages.FEATURED_RETRIEVED, data=EventService(db).featured_for(viewer, query)
    )


@router.get("/{event_id}", response_model=SuccessResponse[EventRead])
def get_event(event_id: UUID, db: DbSessionDep, viewer: EventViewDep) -> SuccessResponse[EventRead]:
    return SuccessResponse(
        message=EventMessages.RETRIEVED, data=EventService(db).get_read(event_id, viewer)
    )


@router.get("/{event_id}/related", response_model=SuccessResponse[list[EventRead]])
def list_related_events(
    event_id: UUID, db: DbSessionDep, viewer: EventViewDep
) -> SuccessResponse[list[EventRead]]:
    return SuccessResponse(
        message=EventMessages.RELATED_RETRIEVED, data=EventService(db).related_to(event_id, viewer)
    )


@router.patch("/{event_id}", response_model=SuccessResponse[EventRead])
def update_event(
    event_id: UUID, payload: EventUpdate, db: DbSessionDep, current_user: EventManageDep
) -> SuccessResponse[EventRead]:
    event = EventService(db).update(event_id, payload, current_user)
    return SuccessResponse(message=EventMessages.UPDATED, data=event)


@router.post("/{event_id}/cancel", response_model=SuccessResponse[EventRead])
def cancel_event(
    event_id: UUID, db: DbSessionDep, current_user: EventManageDep
) -> SuccessResponse[EventRead]:
    event = EventService(db).cancel(event_id, current_user)
    return SuccessResponse(message=EventMessages.CANCELLED, data=event)


@router.post("/{event_id}/feature", response_model=SuccessResponse[EventRead])
def feature_event(
    event_id: UUID, db: DbSessionDep, current_user: EventFeatureDep
) -> SuccessResponse[EventRead]:
    event = EventService(db).set_featured(event_id, True, current_user)
    return SuccessResponse(message=EventMessages.FEATURED, data=event)


@router.delete("/{event_id}/feature", response_model=SuccessResponse[EventRead])
def unfeature_event(
    event_id: UUID, db: DbSessionDep, current_user: EventFeatureDep
) -> SuccessResponse[EventRead]:
    event = EventService(db).set_featured(event_id, False, current_user)
    return SuccessResponse(message=EventMessages.UNFEATURED, data=event)


@router.delete("/{event_id}", response_model=SuccessResponse[None])
def delete_event(
    event_id: UUID, db: DbSessionDep, current_user: EventDeleteDep
) -> SuccessResponse[None]:
    EventService(db).delete(event_id, current_user)
    return SuccessResponse(message=EventMessages.DELETED, data=None)
