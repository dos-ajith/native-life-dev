from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.base import BaseReadSchema
from app.schemas.validators import NonBlankStr

if TYPE_CHECKING:
    from app.models.post_comment import PostComment

PostCommentContent = Annotated[NonBlankStr, Field(max_length=2000)]


class PostCommentRead(BaseReadSchema):
    id: UUID
    post_id: UUID
    user_id: UUID
    parent_id: UUID | None
    content: str
    created_at: datetime
    updated_at: datetime
    replies: list["PostCommentRead"] = []

    @classmethod
    def from_comment(
        cls, comment: "PostComment", replies_by_parent: dict[UUID, list["PostComment"]]
    ) -> "PostCommentRead":
        return cls(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            parent_id=comment.parent_id,
            content=comment.content,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
            replies=[
                cls.from_comment(reply, replies_by_parent)
                for reply in replies_by_parent.get(comment.id, [])
            ],
        )

    @classmethod
    def build_forest(
        cls, roots: list["PostComment"], all_comments: list["PostComment"]
    ) -> list["PostCommentRead"]:
        replies_by_parent: dict[UUID, list[PostComment]] = defaultdict(list)
        for comment in all_comments:
            if comment.parent_id is not None:
                replies_by_parent[comment.parent_id].append(comment)
        return [cls.from_comment(root, replies_by_parent) for root in roots]


class PostCommentCreate(BaseModel):
    content: PostCommentContent
    parent_id: UUID | None = None
