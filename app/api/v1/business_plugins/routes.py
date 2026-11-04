from uuid import UUID

from fastapi import APIRouter

from app.api.deps import ActivityRequestMetaDep, CurrentActiveUserDep, DbSessionDep, SettingsDep
from app.core.messages import BusinessPluginMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.business_plugin import (
    AvailablePluginRead,
    BusinessCapabilitiesRead,
    BusinessPluginRead,
)
from app.schemas.response import SuccessResponse
from app.services.business_plugin_service import BusinessPluginService

router = APIRouter(prefix="/me/businesses/{business_id}", tags=[ApiTag.BUSINESS_PLUGINS])


@router.get("/capabilities", response_model=SuccessResponse[BusinessCapabilitiesRead])
def get_business_capabilities(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    settings: SettingsDep,
    registry: PluginRegistryDep,
) -> SuccessResponse[BusinessCapabilitiesRead]:
    overview = BusinessPluginService(db).overview(business_id, current_user, registry)
    return SuccessResponse(
        message=BusinessPluginMessages.CAPABILITIES_RETRIEVED,
        data=BusinessCapabilitiesRead.from_overview(overview, current_user, settings.api_v1_prefix),
    )


@router.get("/plugins/available", response_model=SuccessResponse[list[AvailablePluginRead]])
def list_available_plugins(
    business_id: UUID,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    registry: PluginRegistryDep,
) -> SuccessResponse[list[AvailablePluginRead]]:
    overview = BusinessPluginService(db).overview(business_id, current_user, registry)
    return SuccessResponse(
        message=BusinessPluginMessages.AVAILABLE_RETRIEVED,
        data=[AvailablePluginRead.from_offer(offer) for offer in overview.offers],
    )


@router.post("/plugins/{plugin_key}", response_model=SuccessResponse[BusinessPluginRead])
def enable_business_plugin(
    business_id: UUID,
    plugin_key: str,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
    registry: PluginRegistryDep,
) -> SuccessResponse[BusinessPluginRead]:
    plugin, business_plugin = BusinessPluginService(db).enable(
        business_id, plugin_key, current_user, registry, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessPluginMessages.ENABLED,
        data=BusinessPluginRead.from_state(business_id, plugin, business_plugin),
    )


@router.delete("/plugins/{plugin_key}", response_model=SuccessResponse[BusinessPluginRead])
def disable_business_plugin(
    business_id: UUID,
    plugin_key: str,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[BusinessPluginRead]:
    plugin, business_plugin = BusinessPluginService(db).disable(
        business_id, plugin_key, current_user, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(
        message=BusinessPluginMessages.DISABLED,
        data=BusinessPluginRead.from_state(business_id, plugin, business_plugin),
    )
