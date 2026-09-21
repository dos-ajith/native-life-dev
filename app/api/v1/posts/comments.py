from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, PaginationDep
from app.core.messages import PostCommentMessages
from app.schemas.pagination import Page
from app.schemas.post_comment import PostCommentCreate, PostCommentRead
from app.schemas.response import SuccessResponse
from app.services.post_comment_service import PostCommentService

router = APIRouter(prefix="/posts", tags=["post-comments"])


@router.post(
    "/{post_id}/comments",
    response_model=SuccessResponse[PostCommentRead],
    status_code=status.HTTP_201_CREATED,
)
def create_comment(
    post_id: UUID,
    payload: PostCommentCreate,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[PostCommentRead]:
    comment = PostCommentService(db).create(post_id, payload, current_user)
    return SuccessResponse(
        message=PostCommentMessages.CREATED, data=PostCommentRead.model_validate(comment)
    )


@router.get("/{post_id}/comments", response_model=SuccessResponse[Page[PostCommentRead]])
def list_comments(
    post_id: UUID, db: DbSessionDep, _: CurrentActiveUserDep, params: PaginationDep
) -> SuccessResponse[Page[PostCommentRead]]:
    items, total = PostCommentService(db).list_for_post(post_id, params)
    page = Page[PostCommentRead].create(items=items, total=total, params=params)
    return SuccessResponse(message=PostCommentMessages.LIST_RETRIEVED, data=page)


@router.delete("/comments/{comment_id}", response_model=SuccessResponse[None])
def delete_comment(
    comment_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[None]:
    PostCommentService(db).delete(comment_id, current_user)
    return SuccessResponse(message=PostCommentMessages.DELETED, data=None)
