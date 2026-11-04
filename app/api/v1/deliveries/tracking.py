from uuid import UUID

from fastapi import APIRouter

from app.api.deps import DbSessionDep
from app.api.v1.deals.permissions import DeliverySettingsManagerDep
from app.core.messages import DeliveryRequestMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery_route import GeoPoint
from app.schemas.response import SuccessResponse
from app.services.delivery_tracking_service import DeliveryTrackingService

router = APIRouter(tags=[ApiTag.DELIVERY_TRACKING])


@router.put("/me/delivery-routes/{route_id}/location", response_model=SuccessResponse[None])
def update_route_location(
    route_id: UUID, payload: GeoPoint, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[None]:
    DeliveryTrackingService(db).update_location(route_id, payload, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.LOCATION_UPDATED, data=None)
