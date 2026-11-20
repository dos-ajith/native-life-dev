from collections.abc import Iterator
from dataclasses import dataclass

from app.ai.voice.avatars import AssistantAvatar, find_avatar
from app.ai.voice.client import VoiceClient, get_voice_client
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import AIMessages

AUDIO_MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav"}
SENTENCE_ENDINGS = (". ", "! ", "? ", "\n")


@dataclass(frozen=True)
class SpeechStream:
    chunks: Iterator[bytes]
    media_type: str


def detect_audio_filename(audio: bytes) -> str | None:
    if audio[:4] == b"RIFF" and audio[8:12] == b"WAVE":
        return "audio.wav"
    if audio[:4] == b"\x1a\x45\xdf\xa3":
        return "audio.webm"
    if audio[:4] == b"OggS":
        return "audio.ogg"
    if audio[:4] == b"fLaC":
        return "audio.flac"
    if audio[4:8] == b"ftyp":
        return "audio.m4a"
    if audio[:3] == b"ID3" or (len(audio) > 1 and audio[0] == 0xFF and audio[1] & 0xE0 == 0xE0):
        return "audio.mp3"
    return None


def speakable_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    sentence_end = max(clipped.rfind(ending) for ending in SENTENCE_ENDINGS)
    if sentence_end > 0:
        return clipped[: sentence_end + 1].strip()
    word_end = clipped.rfind(" ")
    return (clipped[:word_end] if word_end > 0 else clipped).strip()


class VoiceService:
    def __init__(self, settings: Settings, client: VoiceClient | None = None) -> None:
        self._settings = settings
        self._client = client

    def _voice_client(self) -> VoiceClient:
        if self._client is None:
            self._client = get_voice_client()
        return self._client

    def transcribe(self, audio: bytes, language: str | None) -> str:
        if not audio:
            raise BusinessRuleError(AIMessages.AUDIO_EMPTY)
        if len(audio) > self._settings.ai_voice_max_audio_bytes:
            raise BusinessRuleError(AIMessages.AUDIO_TOO_LARGE)
        filename = detect_audio_filename(audio)
        if filename is None:
            raise BusinessRuleError(AIMessages.AUDIO_FORMAT_UNSUPPORTED)
        text = self._voice_client().transcribe(filename, audio, language)
        if not text:
            raise BusinessRuleError(AIMessages.TRANSCRIPT_EMPTY)
        return text

    def stream_speech(self, text: str, avatar_id: str) -> SpeechStream:
        avatar = self.get_avatar(avatar_id)
        voice = avatar.voice_for(self._settings.ai_provider)
        chunks = self._voice_client().open_speech_stream(text, voice)
        return SpeechStream(chunks, AUDIO_MEDIA_TYPES[self._settings.ai_tts_response_format])

    def speakable(self, text: str) -> str:
        return speakable_text(text, self._settings.ai_voice_max_speech_characters)

    def get_avatar(self, avatar_id: str) -> AssistantAvatar:
        avatar = find_avatar(avatar_id)
        if avatar is None:
            raise NotFoundError(AIMessages.AVATAR_NOT_FOUND)
        return avatar
