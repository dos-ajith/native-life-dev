import mimetypes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from app.api.deps import DbSessionDep
from app.api.v1.deliveries.permissions import VerifiedPromoterDep
from app.core.messages import DeliveryRequestMessages
from app.core.openapi_tags import ApiTag
from app.schemas.delivery_request import (
    DeliveryRequestAccept,
    DeliveryRequestListQuery,
    DeliveryRequestRead,
    DeliveryStopRead,
    DeliveryStopsQuery,
)
from app.schemas.response import SuccessResponse
from app.services.delivery_proof_service import DeliveryProofService
from app.services.delivery_request_service import DeliveryRequestService

router = APIRouter(tags=[ApiTag.DELIVERY_REQUESTS])


@router.get("/me/delivery-requests", response_model=SuccessResponse[list[DeliveryRequestRead]])
def list_my_delivery_requests(
    db: DbSessionDep,
    current_user: VerifiedPromoterDep,
    query: Annotated[DeliveryRequestListQuery, Query()],
) -> SuccessResponse[list[DeliveryRequestRead]]:
    requests = DeliveryRequestService(db).list_for_promoter(query.status, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.LIST_RETRIEVED, data=requests)


@router.post(
    "/me/delivery-requests/{request_id}/accept",
    response_model=SuccessResponse[DeliveryRequestRead],
)
def accept_delivery_request(
    request_id: UUID,
    payload: DeliveryRequestAccept,
    db: DbSessionDep,
    current_user: VerifiedPromoterDep,
) -> SuccessResponse[DeliveryRequestRead]:
    accepted = DeliveryRequestService(db).accept(request_id, payload, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.ACCEPTED, data=accepted)


@router.post(
    "/me/delivery-requests/{request_id}/reject",
    response_model=SuccessResponse[DeliveryRequestRead],
)
def reject_delivery_request(
    request_id: UUID, db: DbSessionDep, current_user: VerifiedPromoterDep
) -> SuccessResponse[DeliveryRequestRead]:
    rejected = DeliveryRequestService(db).reject(request_id, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.REJECTED, data=rejected)


@router.get(
    "/me/delivery-routes/{route_id}/stops",
    response_model=SuccessResponse[list[DeliveryStopRead]],
)
def list_route_stops(
    route_id: UUID,
    db: DbSessionDep,
    current_user: VerifiedPromoterDep,
    query: Annotated[DeliveryStopsQuery, Query()],
) -> SuccessResponse[list[DeliveryStopRead]]:
    stops = DeliveryRequestService(db).stops(route_id, query.delivery_date, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.STOPS_RETRIEVED, data=stops)


@router.get("/me/delivery-requests/{request_id}/proof")
def get_delivery_request_proof(
    request_id: UUID, db: DbSessionDep, current_user: VerifiedPromoterDep
) -> FileResponse:
    path = DeliveryProofService(db).path_for_promoter(request_id, current_user)
    return FileResponse(path, media_type=mimetypes.guess_type(path)[0])
