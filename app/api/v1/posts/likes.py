from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep
from app.api.v1.posts.permissions import PostLikeDep
from app.core.messages import PostReactionMessages
from app.core.openapi_tags import ApiTag
from app.schemas.post_reaction import PostReactionCreate
from app.schemas.response import SuccessResponse
from app.services.post_like_service import PostLikeService

router = APIRouter(prefix="/posts", tags=[ApiTag.POSTS])


@router.put("/{post_id}/reactions", response_model=SuccessResponse[None])
def react_to_post(
    post_id: UUID, payload: PostReactionCreate, db: DbSessionDep, current_user: PostLikeDep
) -> SuccessResponse[None]:
    PostLikeService(db).react(post_id, payload.reaction_type, current_user)
    return SuccessResponse(message=PostReactionMessages.REACTED, data=None)


@router.delete("/{post_id}/reactions", response_model=SuccessResponse[None])
def remove_post_reaction(
    post_id: UUID, db: DbSessionDep, current_user: PostLikeDep
) -> SuccessResponse[None]:
    PostLikeService(db).remove_reaction(post_id, current_user)
    return SuccessResponse(message=PostReactionMessages.REACTION_REMOVED, data=None)
