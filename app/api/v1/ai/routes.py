from typing import Annotated

from fastapi import APIRouter, Query, Request, status
from fastapi.responses import StreamingResponse

from app.ai.conversation import AIConversationService
from app.ai.service import AIService
from app.ai.voice.avatars import ASSISTANT_AVATARS
from app.ai.voice.service import VoiceService
from app.ai.welcome import AIWelcomeService
from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.jwt import parse_speech_token
from app.core.messages import AIMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.ai import AIAskRequest, AIAskResponse, AIAvatarRead, AIWelcomeRead
from app.schemas.response import SuccessResponse
from app.services.user_settings_service import UserSettingsService

router = APIRouter(prefix="/ai", tags=[ApiTag.TOOLS_AI])


@router.post("/ask", response_model=SuccessResponse[AIAskResponse], status_code=status.HTTP_200_OK)
def ask_ai(
    payload: AIAskRequest,
    request: Request,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    plugin_registry: PluginRegistryDep,
) -> SuccessResponse[AIAskResponse]:
    conversation = AIConversationService(
        AIService(db, settings, plugin_registry=plugin_registry),
        VoiceService(settings),
        UserSettingsService(db),
        settings,
    )

    def build_speech_url(token: str) -> str:
        return str(request.url_for("stream_ai_speech").include_query_params(token=token))

    result = conversation.ask(payload, current_user, build_speech_url)
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


@router.get("/speech", name="stream_ai_speech", response_class=StreamingResponse)
def stream_ai_speech(
    token: Annotated[str, Query(min_length=1)], settings: SettingsDep
) -> StreamingResponse:
    claims = parse_speech_token(token, settings)
    speech = VoiceService(settings).stream_speech(claims.text, claims.avatar_id)
    return StreamingResponse(speech.chunks, media_type=speech.media_type)
