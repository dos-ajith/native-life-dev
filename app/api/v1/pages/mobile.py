from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import DbSessionDep, require_permission_or_guest
from app.core.messages import PageMessages
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.page import PublishedPageRead
from app.schemas.response import SuccessResponse
from app.services.page_service import PageService

router = APIRouter(prefix="/pages", tags=["pages"])

PageReadDep = Annotated[
    User | None, Depends(require_permission_or_guest(PermissionName.PAGE_READ))
]


@router.get("/{slug}", response_model=SuccessResponse[PublishedPageRead])
def get_published_page(
    slug: str, db: DbSessionDep, _: PageReadDep
) -> SuccessResponse[PublishedPageRead]:
    page = PageService(db).get_published_by_slug(slug)
    return SuccessResponse(
        message=PageMessages.RETRIEVED, data=PublishedPageRead.model_validate(page)
    )
