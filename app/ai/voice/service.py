from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.ai.voice.avatars import AssistantAvatar, find_avatar
from app.ai.voice.client import VoiceClient
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import AIMessages
from app.models.user import User
from app.services.user_settings_service import UserSettingsService

AUDIO_MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}
DEFAULT_AUDIO_FILENAME = "audio"


@dataclass(frozen=True)
class SpeechAudio:
    content: bytes
    media_type: str


class VoiceService:
    def __init__(self, db: Session, settings: Settings, client: VoiceClient | None = None) -> None:
        self._settings = settings
        self._client = client
        self._user_settings = UserSettingsService(db)

    def _voice_client(self) -> VoiceClient:
        if self._client is None:
            self._client = VoiceClient(self._settings)
        return self._client

    def _require_ai_enabled(self, actor: User) -> None:
        if not self._user_settings.get_ai(actor).ai_enabled:
            raise BusinessRuleError(AIMessages.AI_DISABLED_BY_USER)

    def _read_audio(self, upload: UploadFile) -> bytes:
        limit = self._settings.ai_voice_max_audio_bytes
        audio = upload.file.read(limit + 1)
        if not audio:
            raise BusinessRuleError(AIMessages.AUDIO_EMPTY)
        if len(audio) > limit:
            raise BusinessRuleError(AIMessages.AUDIO_TOO_LARGE)
        return audio

    def transcribe(self, upload: UploadFile, language: str | None, actor: User) -> str:
        self._require_ai_enabled(actor)
        audio = self._read_audio(upload)
        text = self._voice_client().transcribe(
            upload.filename or DEFAULT_AUDIO_FILENAME, audio, language
        )
        if not text:
            raise BusinessRuleError(AIMessages.TRANSCRIPT_EMPTY)
        return text

    def speak(self, text: str, avatar_id: str, actor: User) -> SpeechAudio:
        self._require_ai_enabled(actor)
        if len(text) > self._settings.ai_voice_max_speech_characters:
            raise BusinessRuleError(AIMessages.SPEECH_TEXT_TOO_LONG)
        avatar = self._get_avatar(avatar_id)
        voice = avatar.voice_for(self._settings.ai_provider)
        content = self._voice_client().synthesize(text, voice)
        return SpeechAudio(content, AUDIO_MEDIA_TYPES[self._settings.ai_tts_response_format])

    def _get_avatar(self, avatar_id: str) -> AssistantAvatar:
        avatar = find_avatar(avatar_id)
        if avatar is None:
            raise NotFoundError(AIMessages.AVATAR_NOT_FOUND)
        return avatar
