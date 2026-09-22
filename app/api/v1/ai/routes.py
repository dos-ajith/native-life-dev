from fastapi import APIRouter, status

from app.ai.service import AIService
from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import AIMessages
from app.schemas.ai import AIAskRequest, AIAskResponse
from app.schemas.response import SuccessResponse

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/ask", response_model=SuccessResponse[AIAskResponse], status_code=status.HTTP_200_OK)
def ask_ai(
    payload: AIAskRequest,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
) -> SuccessResponse[AIAskResponse]:
    result = AIService(db, settings).ask(payload.prompt, current_user)
    return SuccessResponse(message=AIMessages.RESPONSE_GENERATED, data=result)
