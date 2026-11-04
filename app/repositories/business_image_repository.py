from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.business_image import BusinessImage


class BusinessImageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, image_id: UUID) -> BusinessImage | None:
        return self._db.get(BusinessImage, image_id)

    def list_by_business(self, business_id: UUID) -> list[BusinessImage]:
        return list(
            self._db.scalars(
                select(BusinessImage)
                .where(BusinessImage.business_id == business_id)
                .order_by(BusinessImage.sort_order, BusinessImage.created_at, BusinessImage.id)
            )
        )

    def next_sort_order(self, business_id: UUID) -> int:
        highest = self._db.scalar(
            select(func.max(BusinessImage.sort_order)).where(
                BusinessImage.business_id == business_id
            )
        )
        return 0 if highest is None else highest + 1

    def add(self, image: BusinessImage) -> BusinessImage:
        self._db.add(image)
        self._db.commit()
        self._db.refresh(image)
        return image

    def delete(self, image: BusinessImage) -> None:
        self._db.delete(image)
        self._db.commit()
