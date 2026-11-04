from typing import Annotated

from fastapi import APIRouter, Depends

from app.plugins.sdk import (
    PluginBusiness,
    SuccessResponse,
    User,
    require_business_plugin,
    require_permission,
)

from .messages import HelloMessages
from .permissions import HelloPermission
from .schemas import BusinessGreetingRead, GreetingRead

PLUGIN_KEY = "hello"

GreetingViewerDep = Annotated[User, Depends(require_permission(HelloPermission.GREETING_VIEW))]
HelloBusinessDep = Annotated[PluginBusiness, Depends(require_business_plugin(PLUGIN_KEY))]

router = APIRouter()


@router.get("/greeting", response_model=SuccessResponse[GreetingRead])
def get_greeting(_: GreetingViewerDep) -> SuccessResponse[GreetingRead]:
    return SuccessResponse(
        message=HelloMessages.GREETING_RETRIEVED,
        data=GreetingRead(plugin=PLUGIN_KEY, greeting=HelloMessages.GREETING),
    )


@router.get(
    "/businesses/{business_id}/greeting", response_model=SuccessResponse[BusinessGreetingRead]
)
def get_business_greeting(
    _: GreetingViewerDep, business: HelloBusinessDep
) -> SuccessResponse[BusinessGreetingRead]:
    return SuccessResponse(
        message=HelloMessages.GREETING_RETRIEVED,
        data=BusinessGreetingRead(
            plugin=PLUGIN_KEY,
            greeting=HelloMessages.GREETING,
            business_id=business.id,
            business_name=business.name,
        ),
    )
