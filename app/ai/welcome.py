from sqlalchemy.orm import Session

from app.core.messages import AIWelcomeMessages
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.ai import AISuggestionRead, AIWelcomeRead

SUGGESTION_TEMPLATES = (
    (
        "updates",
        AIWelcomeMessages.UPDATES_TITLE,
        AIWelcomeMessages.UPDATES_SUBTITLE,
        AIWelcomeMessages.UPDATES_PROMPT,
    ),
    (
        "events",
        AIWelcomeMessages.EVENTS_TITLE,
        AIWelcomeMessages.EVENTS_SUBTITLE,
        AIWelcomeMessages.EVENTS_PROMPT,
    ),
    (
        "community_posts",
        AIWelcomeMessages.COMMUNITY_TITLE,
        AIWelcomeMessages.COMMUNITY_SUBTITLE,
        AIWelcomeMessages.COMMUNITY_PROMPT,
    ),
    (
        "find_business",
        AIWelcomeMessages.BUSINESS_TITLE,
        AIWelcomeMessages.BUSINESS_SUBTITLE,
        AIWelcomeMessages.BUSINESS_PROMPT,
    ),
)


class AIWelcomeService:
    def __init__(self, db: Session) -> None:
        self._places = UserNativePlaceRepository(db)

    def build(self, user: User) -> AIWelcomeRead:
        place_name = self._primary_place_name(user)
        area = place_name or AIWelcomeMessages.DEFAULT_AREA
        hint = (
            AIWelcomeMessages.HINT_WITH_PLACE.format(place=place_name)
            if place_name
            else AIWelcomeMessages.HINT_WITHOUT_PLACE
        )
        return AIWelcomeRead(
            greeting=AIWelcomeMessages.GREETING.format(name=user.first_name),
            intro=AIWelcomeMessages.INTRO,
            hint=hint,
            place_name=place_name,
            suggestions_title=AIWelcomeMessages.SUGGESTIONS_TITLE,
            suggestions=[
                AISuggestionRead(
                    id=suggestion_id,
                    title=title,
                    subtitle=subtitle,
                    prompt=prompt.format(area=area),
                )
                for suggestion_id, title, subtitle, prompt in SUGGESTION_TEMPLATES
            ],
        )

    def _primary_place_name(self, user: User) -> str | None:
        for place in self._places.list_by_user(user.id):
            if place.slot == NativePlaceSlot.PRIMARY:
                return place.village.name
        return None
