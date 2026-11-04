from uuid import UUID

from fastapi import APIRouter

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.api.v1.deals.permissions import DeliverySettingsManagerDep
from app.core.messages import DeliveryMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery import DeliveryOptionRead, DeliverySettingsRead, DeliverySettingsUpdate
from app.schemas.response import SuccessResponse
from app.services.deal_service import DealService
from app.services.delivery_settings_service import DeliverySettingsService

router = APIRouter(prefix="/deals/{deal_id}/delivery-options", tags=[ApiTag.DEAL_DELIVERY])
settings_router = APIRouter(prefix="/me/delivery-settings", tags=[ApiTag.DEAL_DELIVERY])


@settings_router.get("", response_model=SuccessResponse[DeliverySettingsRead | None])
def get_my_delivery_settings(
    db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliverySettingsRead | None]:
    settings = DeliverySettingsService(db).get_mine(current_user)
    return SuccessResponse(message=DeliveryMessages.SETTINGS_RETRIEVED, data=settings)


@settings_router.put("", response_model=SuccessResponse[DeliverySettingsRead])
def save_my_delivery_settings(
    payload: DeliverySettingsUpdate, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliverySettingsRead]:
    settings = DeliverySettingsService(db).save(payload, current_user)
    return SuccessResponse(message=DeliveryMessages.SETTINGS_SAVED, data=settings)


@router.get("", response_model=SuccessResponse[list[DeliveryOptionRead]])
def list_deal_delivery_options(
    deal_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[list[DeliveryOptionRead]]:
    options = DealService(db).delivery_options(deal_id, current_user)
    return SuccessResponse(message=DeliveryMessages.OPTIONS_RETRIEVED, data=options)
