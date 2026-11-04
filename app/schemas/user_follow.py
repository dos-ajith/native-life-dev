import enum

from pydantic import BaseModel


class FollowRelationship(enum.StrEnum):
    NONE = "none"
    PENDING = "pending"
    ACCEPTED = "accepted"


class FollowStatusRead(BaseModel):
    is_following: bool
    is_requested: bool


class FollowCountsRead(BaseModel):
    followers_count: int
    following_count: int
