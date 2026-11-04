import enum


class AIResponseStyle(enum.StrEnum):
    CONCISE = "concise"
    BALANCED = "balanced"
    DETAILED = "detailed"


class VisibilityLevel(enum.StrEnum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    PRIVATE = "private"


class MessagePermission(enum.StrEnum):
    EVERYONE = "everyone"
    CONNECTIONS = "connections"


class ProfileVisibility(enum.StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
