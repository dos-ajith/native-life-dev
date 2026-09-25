from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep, PaginationDep
from app.api.v1.posts.permissions import PostSaveDep
from app.core.messages import SavedPostMessages
from app.schemas.pagination import Page
from app.schemas.post import PostDetailRead
from app.schemas.response import SuccessResponse
from app.services.saved_post_service import SavedPostService

router = APIRouter(prefix="/posts", tags=["saved-posts"])
me_router = APIRouter(prefix="/me/saved-posts", tags=["saved-posts"])


@router.post(
    "/{post_id}/save", response_model=SuccessResponse[None], status_code=status.HTTP_201_CREATED
)
def save_post(post_id: UUID, db: DbSessionDep, current_user: PostSaveDep) -> SuccessResponse[None]:
    SavedPostService(db).save(post_id, current_user)
    return SuccessResponse(message=SavedPostMessages.SAVED, data=None)


@router.delete("/{post_id}/save", response_model=SuccessResponse[None])
def unsave_post(
    post_id: UUID, db: DbSessionDep, current_user: PostSaveDep
) -> SuccessResponse[None]:
    SavedPostService(db).unsave(post_id, current_user)
    return SuccessResponse(message=SavedPostMessages.UNSAVED, data=None)


@me_router.get("", response_model=SuccessResponse[Page[PostDetailRead]])
def list_saved_posts(
    db: DbSessionDep, current_user: PostSaveDep, params: PaginationDep
) -> SuccessResponse[Page[PostDetailRead]]:
    items, total = SavedPostService(db).list_saved_posts(current_user, params)
    page = Page[PostDetailRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=SavedPostMessages.LIST_RETRIEVED, data=page)
