from fastapi import APIRouter, status

from app.ai.service import AIService
from app.ai.welcome import AIWelcomeService
from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import AIMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.ai import AIAskRequest, AIAskResponse, AIWelcomeRead
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
