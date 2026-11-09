from dataclasses import dataclass
from enum import StrEnum


class AvatarGender(StrEnum):
    MALE = "male"
    FEMALE = "female"


@dataclass(frozen=True)
class AssistantAvatar:
    id: str
    name: str
    gender: AvatarGender
    openai_voice: str
    groq_voice: str

    def voice_for(self, provider: str) -> str:
        return self.groq_voice if provider == "groq" else self.openai_voice


ASSISTANT_AVATARS: tuple[AssistantAvatar, ...] = (
    AssistantAvatar("arjun", "Arjun", AvatarGender.MALE, "onyx", "austin"),
    AssistantAvatar("anjali", "Anjali", AvatarGender.FEMALE, "nova", "hannah"),
)

DEFAULT_AVATAR_ID = ASSISTANT_AVATARS[0].id


def find_avatar(avatar_id: str) -> AssistantAvatar | None:
    return next((avatar for avatar in ASSISTANT_AVATARS if avatar.id == avatar_id), None)
