from typing import Annotated

from fastapi import APIRouter, Body, status

from app.api.deps import CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import DeviceMessages
from app.core.openapi_tags import ApiTag
from app.schemas.device_token import (
    DeviceTokenRead,
    DeviceTokenRegister,
    DeviceTokenRemove,
    WebPushConfigRead,
)
from app.schemas.response import SuccessResponse
from app.services.device_token_service import DeviceTokenService
from app.services.web_push_config_service import WebPushConfigService

router = APIRouter(prefix="/me/devices", tags=[ApiTag.NOTIFICATIONS])


@router.get("/web-config", response_model=SuccessResponse[WebPushConfigRead])
def get_web_push_config(
    settings: SettingsDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[WebPushConfigRead]:
    return SuccessResponse(
        message=DeviceMessages.WEB_CONFIG_RETRIEVED, data=WebPushConfigService(settings).get()
    )


@router.post(
    "", response_model=SuccessResponse[DeviceTokenRead], status_code=status.HTTP_201_CREATED
)
def register_device(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    payload: Annotated[DeviceTokenRegister, Body()],
) -> SuccessResponse[DeviceTokenRead]:
    device = DeviceTokenService(db).register(current_user, payload)
    return SuccessResponse(
        message=DeviceMessages.REGISTERED, data=DeviceTokenRead.model_validate(device)
    )


@router.delete("", response_model=SuccessResponse[None])
def remove_device(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    payload: Annotated[DeviceTokenRemove, Body()],
) -> SuccessResponse[None]:
    DeviceTokenService(db).remove(current_user, payload.token)
    return SuccessResponse(message=DeviceMessages.REMOVED, data=None)
