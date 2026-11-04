from collections.abc import Sequence
from datetime import date, datetime, time, timedelta
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import EventMessages
from app.core.permissions import PermissionName
from app.core.timezone import app_now, to_naive_app_time
from app.models.event import Event, EventStatus
from app.models.user import User
from app.repositories.event_image_repository import EventImageRepository
from app.repositories.event_repository import EventFilter, EventRepository
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import point_from_coordinates
from app.repositories.user_repository import UserRepository
from app.schemas.event import EventCreate, EventListQuery, EventRead, EventUpdate
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.category_service import CategoryService
from app.services.event_image_service import (
    EventImageService,
    ensure_captions_fit,
    ensure_within_image_limit,
)
from app.services.native_area_resolver import NativeAreaResolver
from app.services.user_settings_service import UserSettingsService

ENTITY_TYPE = "event"
METERS_PER_KM = 1000
DISTANCE_KM_DECIMALS = 2
RELATED_EVENTS_LIMIT = 5
SINGLE_ROW = PaginationParams(page=1, page_size=1)
RELATED_ROWS = PaginationParams(page=1, page_size=RELATED_EVENTS_LIMIT)
SCHEDULE_FIELDS = {"latitude", "longitude", "starts_at", "ends_at"}


class EventService:
    def __init__(self, db: Session) -> None:
        self._events = EventRepository(db)
        self._images = EventImageRepository(db)
        self._image_service = EventImageService(db)
        self._users = UserRepository(db)
        self._categories = CategoryService(db)
        self._areas = NativeAreaResolver(db)
        self._settings = UserSettingsService(db)
        self._activity_logs = ActivityLogService(db)

    def create(
        self,
        payload: EventCreate,
        files: list[UploadFile],
        captions: list[str],
        upload_dir: str,
        actor: User,
    ) -> EventRead:
        ensure_captions_fit(files, captions)
        ensure_within_image_limit(len(files))
        self._categories.ensure_assignable(payload.category_id)
        data = payload.model_dump(exclude=SCHEDULE_FIELDS)
        data["organizer_name"] = payload.organizer_name or f"{actor.first_name} {actor.last_name}"
        data["organizer_phone"] = payload.organizer_phone or actor.phone
        event = self._events.add(
            Event(
                user_id=actor.id,
                location=point_from_coordinates(payload.latitude, payload.longitude),
                starts_at=to_naive_app_time(payload.starts_at),
                ends_at=to_naive_app_time(payload.ends_at),
                **data,
            )
        )
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=event.id,
            metadata={"category_id": str(event.category_id)},
        )
        self._image_service.add(event, files, captions, upload_dir, actor)
        return self.get_read(event.id, actor)

    def get_read(self, event_id: UUID, viewer: User) -> EventRead:
        return self._to_reads([(self._get(event_id), None)], viewer)[0]

    def list_for(
        self, params: PaginationParams, viewer: User, query: EventListQuery
    ) -> tuple[list[EventRead], int]:
        event_filter = EventFilter(
            now=self._now(),
            category_id=query.category_id,
            query=query.q,
            starts_from=self._day_start(query.from_date),
            starts_before=self._day_start(query.to_date, extra_days=1),
        )
        return self._list(params, viewer, query, event_filter)

    def featured_for(self, viewer: User, query: EventListQuery) -> EventRead | None:
        for featured_only in (True, False):
            event_filter = EventFilter(now=self._now(), featured_only=featured_only)
            reads, _ = self._list(SINGLE_ROW, viewer, query, event_filter)
            if reads:
                return reads[0]
        return None

    def related_to(self, event_id: UUID, viewer: User) -> list[EventRead]:
        event = self._get(event_id)
        event_filter = EventFilter(
            now=self._now(), category_id=event.category_id, exclude_id=event.id
        )
        reads, _ = self._list(RELATED_ROWS, viewer, EventListQuery(), event_filter)
        return reads

    def update(self, event_id: UUID, payload: EventUpdate, actor: User) -> EventRead:
        event = self._get(event_id)
        self._ensure_can_modify(event, actor, PermissionName.EVENTS_UPDATE_ANY)
        self._ensure_scheduled(event)
        data = payload.model_dump(exclude=SCHEDULE_FIELDS, exclude_none=True)
        if "category_id" in data and data["category_id"] != event.category_id:
            self._categories.ensure_assignable(data["category_id"])
        starts_at = self._naive_or(payload.starts_at, event.starts_at)
        ends_at = self._naive_or(payload.ends_at, event.ends_at)
        if ends_at <= starts_at:
            raise BusinessRuleError(EventMessages.END_BEFORE_START)
        for field, value in data.items():
            setattr(event, field, value)
        event.starts_at = starts_at
        event.ends_at = ends_at
        if payload.latitude is not None and payload.longitude is not None:
            event.location = point_from_coordinates(payload.latitude, payload.longitude)
        self._events.save(event)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=event.id,
            metadata={"updated_fields": list(payload.model_dump(exclude_none=True).keys())},
        )
        return self.get_read(event.id, actor)

    def cancel(self, event_id: UUID, actor: User) -> EventRead:
        event = self._get(event_id)
        self._ensure_can_modify(event, actor, PermissionName.EVENTS_UPDATE_ANY)
        if event.status == EventStatus.CANCELLED:
            raise BusinessRuleError(EventMessages.ALREADY_CANCELLED)
        event.status = EventStatus.CANCELLED
        event.is_featured = False
        self._events.save(event)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_CANCELLED,
            entity_type=ENTITY_TYPE,
            entity_id=event.id,
        )
        return self.get_read(event.id, actor)

    def set_featured(self, event_id: UUID, featured: bool, actor: User) -> EventRead:
        event = self._get(event_id)
        self._ensure_scheduled(event)
        event.is_featured = featured
        self._events.save(event)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_FEATURED if featured else ActivityAction.EVENT_UNFEATURED,
            entity_type=ENTITY_TYPE,
            entity_id=event.id,
        )
        return self.get_read(event.id, actor)

    def delete(self, event_id: UUID, actor: User) -> None:
        event = self._get(event_id)
        self._ensure_can_modify(event, actor, PermissionName.EVENTS_DELETE_ANY)
        event.deleted_at = app_now()
        event.is_featured = False
        self._events.save(event)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.EVENT_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=event.id,
        )

    def add_images(
        self,
        event_id: UUID,
        files: list[UploadFile],
        captions: list[str],
        upload_dir: str,
        actor: User,
    ) -> EventRead:
        event = self._get(event_id)
        self._ensure_can_modify(event, actor, PermissionName.EVENTS_UPDATE_ANY)
        self._ensure_scheduled(event)
        self._image_service.add(event, files, captions, upload_dir, actor)
        return self.get_read(event.id, actor)

    def remove_image(self, event_id: UUID, image_id: UUID, upload_dir: str, actor: User) -> None:
        event = self._get(event_id)
        self._ensure_can_modify(event, actor, PermissionName.EVENTS_UPDATE_ANY)
        self._ensure_scheduled(event)
        self._image_service.remove(event, image_id, upload_dir, actor)

    def _get(self, event_id: UUID) -> Event:
        event = self._events.get_by_id(event_id)
        if event is None:
            raise NotFoundError(EventMessages.NOT_FOUND)
        return event

    @staticmethod
    def _now() -> datetime:
        return to_naive_app_time(app_now())

    @staticmethod
    def _naive_or(value: datetime | None, current: datetime) -> datetime:
        return current if value is None else to_naive_app_time(value)

    @staticmethod
    def _day_start(day: date | None, extra_days: int = 0) -> datetime | None:
        if day is None:
            return None
        return datetime.combine(day, time.min) + timedelta(days=extra_days)

    @staticmethod
    def _ensure_can_modify(event: Event, actor: User, override_permission: str) -> None:
        if event.user_id != actor.id and not has_permission(actor, override_permission):
            raise AuthorizationError(EventMessages.NOT_OWNER)

    @staticmethod
    def _ensure_scheduled(event: Event) -> None:
        if event.status == EventStatus.CANCELLED:
            raise BusinessRuleError(EventMessages.CANCELLED_READ_ONLY)

    def _list(
        self,
        params: PaginationParams,
        viewer: User,
        query: EventListQuery,
        event_filter: EventFilter,
    ) -> tuple[list[EventRead], int]:
        areas, radius_km = self._list_scope(viewer, query)
        rows, total = self._events.list_upcoming(
            params, event_filter, areas, radius_km * METERS_PER_KM
        )
        distances = [
            None if meters is None else round(meters / METERS_PER_KM, DISTANCE_KM_DECIMALS)
            for _, meters in rows
        ]
        reads = self._to_reads(
            [(event, km) for (event, _), km in zip(rows, distances, strict=True)], viewer
        )
        return reads, total

    def _list_scope(self, viewer: User, query: EventListQuery) -> tuple[list[AreaPoint], float]:
        default_radius_km = float(self._settings.nearby_radius_km(viewer))
        if query.latitude is not None and query.longitude is not None:
            return [
                AreaPoint(query.latitude, query.longitude)
            ], query.radius_km or default_radius_km
        if query.village_id is not None:
            return [self._areas.temporary_area(query.village_id).point], default_radius_km
        return [area.point for area in self._areas.native_areas(viewer)], default_radius_km

    def _to_reads(
        self, rows: Sequence[tuple[Event, float | None]], viewer: User
    ) -> list[EventRead]:
        if not rows:
            return []
        author_ids = list({event.user_id for event, _ in rows})
        authors = {user.id: user for user in self._users.get_by_ids_including_deleted(author_ids)}
        images = self._images.list_by_events([event.id for event, _ in rows])
        return [
            EventRead.from_event(
                event, authors[event.user_id], images.get(event.id, []), viewer, distance_km
            )
            for event, distance_km in rows
        ]
