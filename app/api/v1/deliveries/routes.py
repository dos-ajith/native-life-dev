from uuid import UUID

from fastapi import APIRouter, status

from app.api.deps import DbSessionDep
from app.api.v1.deals.permissions import DeliverySettingsManagerDep
from app.core.messages import DeliveryRouteMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery_route import DeliveryRouteCreate, DeliveryRouteRead, DeliveryRouteUpdate
from app.schemas.response import SuccessResponse
from app.services.delivery_route_service import DeliveryRouteService

router = APIRouter(prefix="/me/delivery-routes", tags=[ApiTag.DELIVERY_ROUTES])


@router.get("", response_model=SuccessResponse[list[DeliveryRouteRead]])
def list_my_routes(
    db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[list[DeliveryRouteRead]]:
    routes = DeliveryRouteService(db).list_for(current_user)
    return SuccessResponse(
        message=DeliveryRouteMessages.LIST_RETRIEVED,
        data=[DeliveryRouteRead.from_route(route) for route in routes],
    )


@router.post(
    "", response_model=SuccessResponse[DeliveryRouteRead], status_code=status.HTTP_201_CREATED
)
def create_my_route(
    payload: DeliveryRouteCreate, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliveryRouteRead]:
    route = DeliveryRouteService(db).create(payload, current_user)
    return SuccessResponse(
        message=DeliveryRouteMessages.CREATED, data=DeliveryRouteRead.from_route(route)
    )


@router.get("/{route_id}", response_model=SuccessResponse[DeliveryRouteRead])
def get_my_route(
    route_id: UUID, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[DeliveryRouteRead]:
    route = DeliveryRouteService(db).get_owned(route_id, current_user)
    return SuccessResponse(
        message=DeliveryRouteMessages.RETRIEVED, data=DeliveryRouteRead.from_route(route)
    )


@router.patch("/{route_id}", response_model=SuccessResponse[DeliveryRouteRead])
def update_my_route(
    route_id: UUID,
    payload: DeliveryRouteUpdate,
    db: DbSessionDep,
    current_user: DeliverySettingsManagerDep,
) -> SuccessResponse[DeliveryRouteRead]:
    route = DeliveryRouteService(db).update(route_id, payload, current_user)
    return SuccessResponse(
        message=DeliveryRouteMessages.UPDATED, data=DeliveryRouteRead.from_route(route)
    )


@router.delete("/{route_id}", response_model=SuccessResponse[None])
def delete_my_route(
    route_id: UUID, db: DbSessionDep, current_user: DeliverySettingsManagerDep
) -> SuccessResponse[None]:
    DeliveryRouteService(db).delete(route_id, current_user)
    return SuccessResponse(message=DeliveryRouteMessages.DELETED, data=None)
