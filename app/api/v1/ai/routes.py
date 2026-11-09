from typing import Annotated

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.ai.service import AIService
from app.ai.voice.avatars import ASSISTANT_AVATARS
from app.ai.voice.service import VoiceService
from app.ai.welcome import AIWelcomeService
from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import AIMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.ai import (
    AIAskRequest,
    AIAskResponse,
    AIAvatarRead,
    AISpeakRequest,
    AITranscriptionRead,
    AIWelcomeRead,
)
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/ai", tags=[ApiTag.TOOLS_AI])


@router.post("/ask", response_model=SuccessResponse[AIAskResponse], status_code=status.HTTP_200_OK)
def ask_ai(
    payload: AIAskRequest,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    plugin_registry: PluginRegistryDep,
) -> SuccessResponse[AIAskResponse]:
    result = AIService(db, settings, plugin_registry=plugin_registry).ask(
        payload.prompt, current_user, payload.location
    )
    return SuccessResponse(message=AIMessages.RESPONSE_GENERATED, data=result)


@router.get("/welcome", response_model=SuccessResponse[AIWelcomeRead])
def get_welcome(
    db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[AIWelcomeRead]:
    return SuccessResponse(
        message=AIMessages.WELCOME_RETRIEVED, data=AIWelcomeService(db).build(current_user)
    )


@router.get("/avatars", response_model=SuccessResponse[list[AIAvatarRead]])
def list_avatars(current_user: CurrentActiveUserDep) -> SuccessResponse[list[AIAvatarRead]]:
    avatars = [
        AIAvatarRead.model_validate(avatar, from_attributes=True) for avatar in ASSISTANT_AVATARS
    ]
    return SuccessResponse(message=AIMessages.AVATARS_RETRIEVED, data=avatars)


@router.post("/voice/transcribe", response_model=SuccessResponse[AITranscriptionRead])
def transcribe_voice(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    audio: Annotated[UploadFile, File()],
    language: Annotated[str | None, Form(max_length=10)] = None,
) -> SuccessResponse[AITranscriptionRead]:
    text = VoiceService(db, settings).transcribe(audio, language, current_user)
    return SuccessResponse(
        message=AIMessages.TRANSCRIPTION_GENERATED, data=AITranscriptionRead(text=text)
    )


@router.post("/voice/speak", response_class=Response)
def speak_text(
    payload: AISpeakRequest,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
) -> Response:
    speech = VoiceService(db, settings).speak(payload.text, payload.avatar_id, current_user)
    return Response(content=speech.content, media_type=speech.media_type)
