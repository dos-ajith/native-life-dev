from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.page import Page
from app.schemas.pagination import PaginationParams


class PageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, page_id: UUID) -> Page | None:
        return self._db.get(Page, page_id)

    def get_by_slug(self, slug: str) -> Page | None:
        return self._db.scalar(select(Page).where(Page.slug == slug))

    def list(self, params: PaginationParams) -> tuple[list[Page], int]:
        total = self._db.scalar(select(func.count()).select_from(Page)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Page).order_by(Page.created_at.desc()).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total

    def add(self, page: Page) -> Page:
        self._db.add(page)
        self._db.commit()
        self._db.refresh(page)
        return page

    def save(self, page: Page) -> Page:
        self._db.commit()
        self._db.refresh(page)
        return page

    def delete(self, page: Page) -> None:
        self._db.delete(page)
        self._db.commit()
