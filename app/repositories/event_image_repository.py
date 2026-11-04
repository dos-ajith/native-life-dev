from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.event_image import EventImage


class EventImageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_in_event(self, event_id: UUID, image_id: UUID) -> EventImage | None:
        return self._db.scalar(
            select(EventImage).where(EventImage.id == image_id, EventImage.event_id == event_id)
        )

    def list_by_events(self, event_ids: Sequence[UUID]) -> dict[UUID, list[EventImage]]:
        images: dict[UUID, list[EventImage]] = defaultdict(list)
        rows = self._db.scalars(
            select(EventImage)
            .where(EventImage.event_id.in_(event_ids))
            .order_by(EventImage.sort_order, EventImage.created_at, EventImage.id)
        )
        for image in rows:
            images[image.event_id].append(image)
        return images

    def count(self, event_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count()).select_from(EventImage).where(EventImage.event_id == event_id)
            )
            or 0
        )

    def next_sort_order(self, event_id: UUID) -> int:
        highest = self._db.scalar(
            select(func.max(EventImage.sort_order)).where(EventImage.event_id == event_id)
        )
        return 0 if highest is None else highest + 1

    def add(self, image: EventImage) -> EventImage:
        self._db.add(image)
        self._db.commit()
        self._db.refresh(image)
        return image

    def delete(self, image: EventImage) -> None:
        self._db.delete(image)
        self._db.commit()
