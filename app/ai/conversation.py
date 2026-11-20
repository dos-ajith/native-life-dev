from collections.abc import Callable

from app.ai.service import AIService
from app.ai.voice.service import VoiceService
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.jwt import create_speech_token
from app.core.messages import AIMessages
from app.models.user import User
from app.schemas.ai import AIAskMode, AIAskRequest, AIAskResponse
from app.services.user_settings_service import UserSettingsService

SpeechUrlBuilder = Callable[[str], str]


class AIConversationService:
    def __init__(
        self,
        ai: AIService,
        voice: VoiceService,
        user_settings: UserSettingsService,
        settings: Settings,
    ) -> None:
        self._ai = ai
        self._voice = voice
        self._user_settings = user_settings
        self._settings = settings

    def ask(
        self, request: AIAskRequest, actor: User, build_speech_url: SpeechUrlBuilder
    ) -> AIAskResponse:
        if request.mode == AIAskMode.CHAT:
            return self._ai.ask(self._require_prompt(request), actor, request.location)
        return self._ask_live(request, actor, build_speech_url)

    def _ask_live(
        self, request: AIAskRequest, actor: User, build_speech_url: SpeechUrlBuilder
    ) -> AIAskResponse:
        if not self._user_settings.get_ai(actor).ai_enabled:
            raise BusinessRuleError(AIMessages.AI_DISABLED_BY_USER)
        avatar = self._voice.get_avatar(request.avatar_id)
        transcript = None
        if request.audio_base64 is not None:
            transcript = self._voice.transcribe(request.audio_base64, request.language)
        prompt = transcript or self._require_prompt(request)
        response = self._ai.ask(prompt, actor, request.location, spoken=True)
        token = create_speech_token(
            actor.id, self._voice.speakable(response.answer), avatar.id, self._settings
        )
        return response.model_copy(
            update={"transcript": transcript, "audio_url": build_speech_url(token)}
        )

    def _require_prompt(self, request: AIAskRequest) -> str:
        if request.prompt is None:
            raise BusinessRuleError(AIMessages.PROMPT_REQUIRED)
        return request.prompt
