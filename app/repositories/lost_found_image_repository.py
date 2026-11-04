from collections import defaultdict
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.lost_found_image import LostFoundImage


class LostFoundImageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_in_item(self, item_id: UUID, image_id: UUID) -> LostFoundImage | None:
        return self._db.scalar(
            select(LostFoundImage).where(
                LostFoundImage.id == image_id, LostFoundImage.item_id == item_id
            )
        )

    def list_by_items(self, item_ids: Sequence[UUID]) -> dict[UUID, list[LostFoundImage]]:
        images: dict[UUID, list[LostFoundImage]] = defaultdict(list)
        rows = self._db.scalars(
            select(LostFoundImage)
            .where(LostFoundImage.item_id.in_(item_ids))
            .order_by(LostFoundImage.sort_order, LostFoundImage.created_at, LostFoundImage.id)
        )
        for image in rows:
            images[image.item_id].append(image)
        return images

    def count(self, item_id: UUID) -> int:
        return (
            self._db.scalar(
                select(func.count())
                .select_from(LostFoundImage)
                .where(LostFoundImage.item_id == item_id)
            )
            or 0
        )

    def next_sort_order(self, item_id: UUID) -> int:
        highest = self._db.scalar(
            select(func.max(LostFoundImage.sort_order)).where(LostFoundImage.item_id == item_id)
        )
        return 0 if highest is None else highest + 1

    def add(self, image: LostFoundImage) -> LostFoundImage:
        self._db.add(image)
        self._db.commit()
        self._db.refresh(image)
        return image

    def delete(self, image: LostFoundImage) -> None:
        self._db.delete(image)
        self._db.commit()
