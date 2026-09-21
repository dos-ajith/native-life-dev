from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.page import PageStatus
from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

PageTitle = Annotated[NonBlankStr, Field(max_length=255)]


class PageRead(BaseReadSchema):
    id: UUID
    title: str
    slug: str
    content: str | None
    image_url: str | None
    status: PageStatus
    created_by: UUID | None
    updated_by: UUID | None
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None


class PageCreate(BaseModel):
    title: PageTitle
    content: str | None = None
    status: PageStatus = PageStatus.DRAFT


class PageUpdate(BaseModel):
    title: PageTitle | None = None
    content: str | None = None
    status: PageStatus | None = None
