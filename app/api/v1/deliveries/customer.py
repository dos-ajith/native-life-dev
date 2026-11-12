from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.core.messages import DeliveryMessages, DeliveryRequestMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery_request import (
    DeliveryRequestRead,
    DeliveryReRequest,
    EligibleRouteListQuery,
    EligibleRouteRead,
    NearbyRouteListQuery,
    NearbyRouteRead,
    NearMissRouteListQuery,
    NearMissRouteRead,
)
from app.schemas.response import SuccessResponse
from app.services.delivery_request_service import DeliveryRequestService
from app.services.eligible_route_service import EligibleRouteService

router = APIRouter(tags=[ApiTag.DELIVERY_CUSTOMER])


@router.get("/delivery/eligible-routes", response_model=SuccessResponse[list[EligibleRouteRead]])
def list_eligible_routes(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    query: Annotated[EligibleRouteListQuery, Query()],
) -> SuccessResponse[list[EligibleRouteRead]]:
    routes = EligibleRouteService(db).list_for(
        query.option, query.address_id, query.deal_id, current_user
    )
    return SuccessResponse(message=DeliveryMessages.ELIGIBLE_ROUTES_RETRIEVED, data=routes)


@router.get(
    "/delivery/eligible-routes/nearby", response_model=SuccessResponse[list[NearbyRouteRead]]
)
def list_nearby_routes(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    query: Annotated[NearbyRouteListQuery, Query()],
) -> SuccessResponse[list[NearbyRouteRead]]:
    routes = EligibleRouteService(db).list_near(query.option, query.latitude, query.longitude)
    return SuccessResponse(message=DeliveryMessages.NEARBY_ROUTES_RETRIEVED, data=routes)


@router.get(
    "/delivery/eligible-routes/near-misses",
    response_model=SuccessResponse[list[NearMissRouteRead]],
)
def list_near_miss_routes(
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
    query: Annotated[NearMissRouteListQuery, Query()],
) -> SuccessResponse[list[NearMissRouteRead]]:
    routes = EligibleRouteService(db).list_near_misses(query.option, query.address_id, current_user)
    return SuccessResponse(message=DeliveryMessages.NEAR_MISS_ROUTES_RETRIEVED, data=routes)


@router.get("/me/orders/{order_id}/delivery", response_model=SuccessResponse[DeliveryRequestRead])
def get_my_order_delivery(
    order_id: UUID, db: DbSessionDep, current_user: CurrentActiveUserDep
) -> SuccessResponse[DeliveryRequestRead]:
    delivery = DeliveryRequestService(db).get_for_order(order_id, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.RETRIEVED, data=delivery)


@router.post(
    "/me/orders/{order_id}/delivery/re-request",
    response_model=SuccessResponse[DeliveryRequestRead],
)
def re_request_my_order_delivery(
    order_id: UUID,
    payload: DeliveryReRequest,
    db: DbSessionDep,
    current_user: CurrentActiveUserDep,
) -> SuccessResponse[DeliveryRequestRead]:
    delivery = DeliveryRequestService(db).re_request(order_id, payload, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.RE_REQUESTED, data=delivery)
