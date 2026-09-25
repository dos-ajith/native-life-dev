from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.collection import Collection
from app.schemas.pagination import PaginationParams


class CollectionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, collection_id: UUID) -> Collection | None:
        return self._db.scalar(select(Collection).where(Collection.id == collection_id))

    def list_by_user(
        self, user_id: UUID, params: PaginationParams
    ) -> tuple[list[Collection], int]:
        conditions = [Collection.user_id == user_id]
        total = (
            self._db.scalar(select(func.count()).select_from(Collection).where(*conditions)) or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Collection)
            .where(*conditions)
            .order_by(Collection.created_at.desc())
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, collection: Collection) -> Collection:
        self._db.add(collection)
        self._db.commit()
        self._db.refresh(collection)
        return collection

    def save(self, collection: Collection) -> Collection:
        self._db.commit()
        self._db.refresh(collection)
        return collection

    def delete(self, collection: Collection) -> None:
        self._db.delete(collection)
        self._db.commit()
