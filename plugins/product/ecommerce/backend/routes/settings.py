from fastapi import APIRouter

from app.plugins.sdk import DbSessionDep, SuccessResponse

from ..messages import EcommerceMessages
from ..schemas.settings import SettingsRead, SettingsUpdate
from ..services.settings_service import SettingsService
from .dependencies import BusinessDep, SettingsManagerDep, SettingsViewerDep

router = APIRouter()


@router.get("/businesses/{business_id}/settings", response_model=SuccessResponse[SettingsRead])
def get_settings(
    _: SettingsViewerDep, business: BusinessDep, db: DbSessionDep
) -> SuccessResponse[SettingsRead]:
    return SuccessResponse(
        message=EcommerceMessages.SETTINGS_RETRIEVED, data=SettingsService(db).get(business.id)
    )


@router.put("/businesses/{business_id}/settings", response_model=SuccessResponse[SettingsRead])
def update_settings(
    actor: SettingsManagerDep, business: BusinessDep, db: DbSessionDep, payload: SettingsUpdate
) -> SuccessResponse[SettingsRead]:
    return SuccessResponse(
        message=EcommerceMessages.SETTINGS_UPDATED,
        data=SettingsService(db).update(business.id, payload, actor),
    )
