from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, case, func, null, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.event import Event, EventStatus
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import as_geography, point_from_coordinates
from app.schemas.pagination import PaginationParams


@dataclass(frozen=True)
class EventFilter:
    now: datetime
    category_id: UUID | None = None
    query: str | None = None
    starts_from: datetime | None = None
    starts_before: datetime | None = None
    featured_only: bool = False
    exclude_id: UUID | None = None


class EventRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, event_id: UUID) -> Event | None:
        return self._db.scalar(
            select(Event)
            .options(joinedload(Event.category))
            .where(Event.id == event_id, Event.deleted_at.is_(None))
        )

    def list_upcoming(
        self,
        params: PaginationParams,
        event_filter: EventFilter,
        areas: Sequence[AreaPoint],
        radius_meters: float,
    ) -> tuple[Sequence[tuple[Event, float | None]], int]:
        location = as_geography(Event.location)
        points = [as_geography(point_from_coordinates(a.latitude, a.longitude)) for a in areas]
        within = [func.ST_DWithin(location, point, radius_meters) for point in points]
        conditions = self._conditions(event_filter)
        distance: ColumnElement[Any] = null()
        if within:
            conditions.append(or_(*within))
            distance = case(
                *(
                    (condition, func.ST_Distance(location, point))
                    for condition, point in zip(within, points, strict=True)
                )
            )
        total = self._db.scalar(select(func.count()).select_from(Event).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        rows = self._db.execute(
            select(Event, distance.label("distance_meters"))
            .options(joinedload(Event.category))
            .where(*conditions)
            .order_by(Event.starts_at, Event.id)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return [(event, meters) for event, meters in rows], total

    def add(self, event: Event) -> Event:
        self._db.add(event)
        self._db.commit()
        self._db.refresh(event)
        return event

    def save(self, event: Event) -> Event:
        self._db.commit()
        self._db.refresh(event)
        return event

    @staticmethod
    def _conditions(event_filter: EventFilter) -> list[ColumnElement[bool]]:
        conditions: list[ColumnElement[bool]] = [
            Event.deleted_at.is_(None),
            Event.status == EventStatus.SCHEDULED,
            Event.ends_at >= event_filter.now,
        ]
        if event_filter.category_id is not None:
            conditions.append(Event.category_id == event_filter.category_id)
        if event_filter.starts_from is not None:
            conditions.append(Event.starts_at >= event_filter.starts_from)
        if event_filter.starts_before is not None:
            conditions.append(Event.starts_at < event_filter.starts_before)
        if event_filter.featured_only:
            conditions.append(Event.is_featured.is_(True))
        if event_filter.exclude_id is not None:
            conditions.append(Event.id != event_filter.exclude_id)
        if event_filter.query:
            pattern = f"%{event_filter.query}%"
            conditions.append(
                or_(
                    Event.title.ilike(pattern),
                    Event.description.ilike(pattern),
                    Event.venue_name.ilike(pattern),
                )
            )
        return conditions
