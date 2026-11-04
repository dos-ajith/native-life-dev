from collections import defaultdict
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseReadSchema
from app.schemas.post import PostAuthorRead
from app.schemas.validators import NonBlankStr
from app.utils.relative_time import format_relative_time

if TYPE_CHECKING:
    from app.models.post_comment import PostComment
    from app.models.user import User

PostCommentContent = Annotated[NonBlankStr, Field(max_length=2000)]


class PostCommentRead(BaseReadSchema):
    id: UUID
    post_id: UUID
    parent_id: UUID | None
    author: PostAuthorRead
    content: str
    created_at_relative: str
    replies: list["PostCommentRead"] = []

    @classmethod
    def from_comment(
        cls,
        comment: "PostComment",
        replies_by_parent: dict[UUID, list["PostComment"]],
        authors: dict[UUID, "User"],
    ) -> "PostCommentRead":
        return cls(
            id=comment.id,
            post_id=comment.post_id,
            parent_id=comment.parent_id,
            author=PostAuthorRead.from_user(authors[comment.user_id]),
            content=comment.content,
            created_at_relative=format_relative_time(comment.created_at),
            replies=[
                cls.from_comment(reply, replies_by_parent, authors)
                for reply in replies_by_parent.get(comment.id, [])
            ],
        )

    @classmethod
    def build_forest(
        cls,
        roots: list["PostComment"],
        all_comments: list["PostComment"],
        authors: dict[UUID, "User"],
    ) -> list["PostCommentRead"]:
        replies_by_parent: dict[UUID, list[PostComment]] = defaultdict(list)
        for comment in all_comments:
            if comment.parent_id is not None:
                replies_by_parent[comment.parent_id].append(comment)
        return [cls.from_comment(root, replies_by_parent, authors) for root in roots]


class PostCommentCreate(BaseModel):
    content: PostCommentContent
    parent_id: UUID | None = None
