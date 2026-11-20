from collections.abc import Iterator
from contextlib import ExitStack
from functools import lru_cache
from typing import Final, Literal

from openai import OpenAI, omit

from app.ai.client import build_sdk_client, call_with_provider_error_handling
from app.ai.voice.transcode import ensure_mp3_encoder_available, wav_stream_to_mp3
from app.core.config import Settings, get_settings

SPEECH_CHUNK_BYTES = 4096
GROQ_PROVIDER = "groq"
GROQ_SPEECH_FORMAT: Final[Literal["wav"]] = "wav"
MP3_FORMAT: Final[Literal["mp3"]] = "mp3"


class VoiceClient:
    def __init__(self, settings: Settings, sdk_client: OpenAI | None = None) -> None:
        self._sdk = sdk_client or build_sdk_client(settings)
        self._stt_model = settings.ai_stt_model
        self._tts_model = settings.ai_tts_model
        self._transcode_to_mp3 = (
            settings.ai_provider == GROQ_PROVIDER and settings.ai_tts_response_format == MP3_FORMAT
        )
        self._response_format = (
            GROQ_SPEECH_FORMAT if self._transcode_to_mp3 else settings.ai_tts_response_format
        )

    def transcribe(self, filename: str, audio: bytes, language: str | None) -> str:
        result = call_with_provider_error_handling(
            lambda: self._sdk.audio.transcriptions.create(
                model=self._stt_model,
                file=(filename, audio),
                language=language or omit,
            )
        )
        return str(result.text).strip()

    def open_speech_stream(self, text: str, voice: str) -> Iterator[bytes]:
        if self._transcode_to_mp3:
            ensure_mp3_encoder_available()
        request = self._sdk.audio.speech.with_streaming_response.create(
            model=self._tts_model,
            voice=voice,
            input=text,
            response_format=self._response_format,
        )
        stack = ExitStack()
        response = call_with_provider_error_handling(lambda: stack.enter_context(request))

        def chunks() -> Iterator[bytes]:
            with stack:
                raw = response.iter_bytes(SPEECH_CHUNK_BYTES)
                yield from wav_stream_to_mp3(raw) if self._transcode_to_mp3 else raw

        return chunks()


@lru_cache
def get_voice_client() -> VoiceClient:
    return VoiceClient(get_settings())
