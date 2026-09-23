from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep
from app.api.v1.posts.permissions import PostLikeDep
from app.core.messages import PostLikeMessages
from app.schemas.response import SuccessResponse
from app.services.post_like_service import PostLikeService

router = APIRouter(prefix="/posts", tags=["post-likes"])


@router.post(
    "/{post_id}/likes", response_model=SuccessResponse[None], status_code=status.HTTP_201_CREATED
)
def like_post(
    post_id: UUID, db: DbSessionDep, current_user: PostLikeDep
) -> SuccessResponse[None]:
    PostLikeService(db).like(post_id, current_user)
    return SuccessResponse(message=PostLikeMessages.LIKED, data=None)


@router.delete("/{post_id}/likes", response_model=SuccessResponse[None])
def unlike_post(
    post_id: UUID, db: DbSessionDep, current_user: PostLikeDep
) -> SuccessResponse[None]:
    PostLikeService(db).unlike(post_id, current_user)
    return SuccessResponse(message=PostLikeMessages.UNLIKED, data=None)
