import enum


class AIResponseStyle(enum.StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class VisibilityLevel(enum.StrEnum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"
