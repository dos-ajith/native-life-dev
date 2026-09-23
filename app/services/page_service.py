from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PageMessages
from app.core.storage import delete_media_file, save_profile_image
from app.models.page import Page, PageStatus
from app.models.user import User
from app.repositories.page_repository import PageRepository
from app.schemas.page import PageCreate, PageUpdate
from app.schemas.pagination import PaginationParams
from app.utils.slug import slugify


class PageService:
    def __init__(self, db: Session) -> None:
        self._pages = PageRepository(db)

    def create(self, payload: PageCreate, acting_user: User) -> Page:
        slug = slugify(payload.title)
        if self._pages.get_by_slug(slug) is not None:
            raise BusinessRuleError(PageMessages.SLUG_TAKEN)
        page = Page(
            title=payload.title,
            slug=slug,
            content=payload.content,
            status=payload.status,
            created_by=acting_user.id,
            updated_by=acting_user.id,
            published_at=datetime.now(UTC) if payload.status == PageStatus.PUBLISHED else None,
        )
        return self._pages.add(page)

    def get(self, page_id: UUID) -> Page:
        page = self._pages.get_by_id(page_id)
        if page is None:
            raise NotFoundError(PageMessages.NOT_FOUND)
        return page

    def get_by_slug(self, slug: str) -> Page:
        page = self._pages.get_by_slug(slug)
        if page is None:
            raise NotFoundError(PageMessages.NOT_FOUND)
        return page

    def get_published_by_slug(self, slug: str) -> Page:
        page = self.get_by_slug(slug)
        if page.status != PageStatus.PUBLISHED:
            raise NotFoundError(PageMessages.NOT_FOUND)
        return page

    def list(self, params: PaginationParams) -> tuple[list[Page], int]:
        return self._pages.list(params)

    def update(self, page_id: UUID, payload: PageUpdate, acting_user: User) -> Page:
        page = self.get(page_id)
        data: dict[str, Any] = payload.model_dump(exclude_none=True)
        status = data.get("status")
        if status == PageStatus.PUBLISHED and page.status != PageStatus.PUBLISHED:
            page.published_at = datetime.now(UTC)
        for field, value in data.items():
            setattr(page, field, value)
        page.updated_by = acting_user.id
        return self._pages.save(page)

    def delete(self, page_id: UUID) -> None:
        page = self.get(page_id)
        self._pages.delete(page)

    def update_image(self, page_id: UUID, image: UploadFile, upload_dir: str) -> Page:
        page = self.get(page_id)
        previous_url = page.image_url
        page.image_url = save_profile_image(image, upload_dir)
        saved = self._pages.save(page)
        if previous_url is not None:
            delete_media_file(previous_url, upload_dir)
        return saved
