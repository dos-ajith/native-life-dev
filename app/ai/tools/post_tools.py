from uuid import UUID

from pydantic import BaseModel, Field

from app.ai.tools.base import AITool, ToolContext
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.messages import AIMessages, PostMessages
from app.models.post import PostStatus
from app.models.user import UserType
from app.schemas.ai import PostReferenceRead
from app.schemas.pagination import PaginationParams
from app.schemas.post_comment import PostCommentRead
from app.schemas.tag import TagRead
from app.services.post_comment_service import PostCommentService
from app.services.post_service import PostService

_MAX_PAGE_SIZE = 50
_MAX_POST_PAGE_SIZE = 5


class GetPostArgs(BaseModel):
    post_id: UUID


class GetPostTool(AITool[GetPostArgs]):
    name = "get_post"
    description = (
        "Retrieve a single published Native Life post by id, including its author, "
        "a short content summary, primary image, and tags. Draft and scheduled posts "
        "are not visible to this tool."
    )
    args_model = GetPostArgs

    def execute(self, context: ToolContext, arguments: GetPostArgs) -> PostReferenceRead:
        detail = PostService(context.db).get_detail(arguments.post_id)
        if detail.status != PostStatus.PUBLISHED:
            raise NotFoundError(PostMessages.NOT_FOUND)
        return PostReferenceRead.from_detail(detail)


class SearchPostsArgs(BaseModel):
    query: str | None = Field(
        default=None,
        description=(
            "Free-text keywords to match against post title, content, and tags "
            "(e.g. 'kerala traditional food'). Matches loosely, so prefer this "
            "over guessing exact tag names — it usually succeeds on the first try."
        ),
    )
    tags: list[str] | None = Field(
        default=None,
        description="Exact tag names to filter by, only when you already know them precisely.",
    )
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=_MAX_POST_PAGE_SIZE, ge=1, le=_MAX_POST_PAGE_SIZE)


class SearchPostsResult(BaseModel):
    items: list[PostReferenceRead]
    total: int


class SearchPostsTool(AITool[SearchPostsArgs]):
    name = "search_posts"
    description = (
        "Search published Native Life posts by free-text query and/or exact tag "
        "names. Returns up to 5 compact post references (id, title, summary, "
        "author, image, tags), ranked by likes (most-liked first) — use get_post "
        "for the full content of a specific result."
    )
    args_model = SearchPostsArgs

    def execute(self, context: ToolContext, arguments: SearchPostsArgs) -> SearchPostsResult:
        params = PaginationParams(page=arguments.page, page_size=arguments.page_size)
        items, total = PostService(context.db).search_with_details(
            params, arguments.tags, arguments.query, order_by_likes=True
        )
        return SearchPostsResult(
            items=[PostReferenceRead.from_detail(item) for item in items], total=total
        )


class GetPostCommentsArgs(BaseModel):
    post_id: UUID
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=_MAX_PAGE_SIZE)


class GetPostCommentsResult(BaseModel):
    items: list[PostCommentRead]
    total: int


class GetPostCommentsTool(AITool[GetPostCommentsArgs]):
    name = "get_post_comments"
    description = "Retrieve comments for a post, threaded by parent comment."
    args_model = GetPostCommentsArgs

    def execute(
        self, context: ToolContext, arguments: GetPostCommentsArgs
    ) -> GetPostCommentsResult:
        params = PaginationParams(page=arguments.page, page_size=arguments.page_size)
        items, total = PostCommentService(context.db).list_for_post(arguments.post_id, params)
        return GetPostCommentsResult(items=items, total=total)


class GetPostTagsArgs(BaseModel):
    post_id: UUID


class GetPostTagsResult(BaseModel):
    items: list[TagRead]


class GetPostTagsTool(AITool[GetPostTagsArgs]):
    name = "get_post_tags"
    description = "Retrieve the tags attached to a post."
    args_model = GetPostTagsArgs

    def execute(self, context: ToolContext, arguments: GetPostTagsArgs) -> GetPostTagsResult:
        tags = PostService(context.db).list_tags(arguments.post_id)
        return GetPostTagsResult(items=[TagRead.model_validate(tag) for tag in tags])


class GetUserPostsArgs(BaseModel):
    user_id: UUID
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=_MAX_POST_PAGE_SIZE, ge=1, le=_MAX_POST_PAGE_SIZE)


class GetUserPostsResult(BaseModel):
    items: list[PostReferenceRead]
    total: int


class GetUserPostsTool(AITool[GetUserPostsArgs]):
    name = "get_user_posts"
    description = (
        "Retrieve up to 5 compact post references (id, title, summary, author, image, "
        "tags) for the published posts authored by a specific user, ranked by likes "
        "(most-liked first). Draft and scheduled posts are not visible to this tool."
    )
    args_model = GetUserPostsArgs

    def execute(self, context: ToolContext, arguments: GetUserPostsArgs) -> GetUserPostsResult:
        if arguments.user_id != context.actor.id and context.actor.user_type != UserType.PRIVATE:
            raise AuthorizationError(AIMessages.USER_POSTS_FORBIDDEN)
        params = PaginationParams(page=arguments.page, page_size=arguments.page_size)
        items, total = PostService(context.db).list_by_user_with_details(
            arguments.user_id, params, published_only=True, order_by_likes=True
        )
        return GetUserPostsResult(
            items=[PostReferenceRead.from_detail(item) for item in items], total=total
        )
