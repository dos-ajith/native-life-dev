from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep
from app.api.v1.posts.permissions import PostShareDep
from app.core.messages import PostShareMessages
from app.schemas.post_share import PostShareCreate
from app.schemas.response import SuccessResponse
from app.services.post_share_service import PostShareService

router = APIRouter(prefix="/posts", tags=["post-shares"])


@router.post(
    "/{post_id}/shares",
    response_model=SuccessResponse[None],
    status_code=status.HTTP_201_CREATED,
)
def share_post(
    post_id: UUID,
    db: DbSessionDep,
    current_user: PostShareDep,
    payload: PostShareCreate | None = None,
) -> SuccessResponse[None]:
    utm_source = payload.utm_source if payload is not None else None
    PostShareService(db).share(post_id, current_user, utm_source)
    return SuccessResponse(message=PostShareMessages.SHARED, data=None)
