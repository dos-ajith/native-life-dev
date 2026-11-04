from pydantic import BaseModel

from app.models.post_like import ReactionType


class PostReactionCreate(BaseModel):
    reaction_type: ReactionType = ReactionType.LIKE
