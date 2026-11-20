import mimetypes
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import DbSessionDep, SettingsDep
from app.api.v1.deliveries.permissions import DeliveryTeamMemberDep
from app.core.messages import DeliveryRequestMessages, DeliveryTeamMessages
from app.core.openapi_tags import ApiTag
from app.schemas.courier import CourierProfileRead, CourierRequestListQuery, CourierRequestRead
from app.schemas.delivery_route import DeliveryRouteRead
from app.schemas.response import SuccessResponse
from app.services.courier_request_service import CourierRequestService
from app.services.courier_service import CourierService
from app.services.delivery_handover_service import DeliveryHandoverService
from app.services.delivery_proof_service import DeliveryProofService
from app.services.handover_otp import HANDOVER_OTP_LENGTH

OTP_PATTERN = rf"^[0-9]{{{HANDOVER_OTP_LENGTH}}}$"

router = APIRouter(prefix="/me/courier", tags=[ApiTag.DELIVERY_COURIER])


@router.get("/profile", response_model=SuccessResponse[CourierProfileRead])
def get_my_courier_profile(
    db: DbSessionDep, current_user: DeliveryTeamMemberDep
) -> SuccessResponse[CourierProfileRead]:
    return SuccessResponse(
        message=DeliveryTeamMessages.PROFILE_RETRIEVED,
        data=CourierService(db).profile(current_user),
    )


@router.get("/routes", response_model=SuccessResponse[list[DeliveryRouteRead]])
def list_my_assigned_routes(
    db: DbSessionDep, current_user: DeliveryTeamMemberDep
) -> SuccessResponse[list[DeliveryRouteRead]]:
    routes = CourierService(db).list_routes(current_user)
    return SuccessResponse(
        message=DeliveryTeamMessages.ROUTES_RETRIEVED,
        data=[DeliveryRouteRead.from_route(route) for route in routes],
    )


@router.get("/routes/{route_id}", response_model=SuccessResponse[DeliveryRouteRead])
def get_my_assigned_route(
    route_id: UUID, db: DbSessionDep, current_user: DeliveryTeamMemberDep
) -> SuccessResponse[DeliveryRouteRead]:
    route = CourierService(db).get_route(route_id, current_user)
    return SuccessResponse(
        message=DeliveryTeamMessages.ROUTE_RETRIEVED, data=DeliveryRouteRead.from_route(route)
    )


@router.get("/requests", response_model=SuccessResponse[list[CourierRequestRead]])
def list_my_assigned_requests(
    db: DbSessionDep,
    current_user: DeliveryTeamMemberDep,
    query: Annotated[CourierRequestListQuery, Query()],
) -> SuccessResponse[list[CourierRequestRead]]:
    requests = CourierRequestService(db).list_for(current_user, query.status, query.delivery_date)
    return SuccessResponse(message=DeliveryTeamMessages.REQUESTS_RETRIEVED, data=requests)


@router.get("/requests/{request_id}", response_model=SuccessResponse[CourierRequestRead])
def get_my_assigned_request(
    request_id: UUID, db: DbSessionDep, current_user: DeliveryTeamMemberDep
) -> SuccessResponse[CourierRequestRead]:
    request = CourierRequestService(db).get_for(request_id, current_user)
    return SuccessResponse(message=DeliveryTeamMessages.REQUEST_RETRIEVED, data=request)


@router.post("/requests/{request_id}/start", response_model=SuccessResponse[CourierRequestRead])
def start_my_delivery(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: DeliveryTeamMemberDep,
) -> SuccessResponse[CourierRequestRead]:
    DeliveryHandoverService(db, settings.private_upload_dir).start(request_id, current_user)
    request = CourierRequestService(db).get_for(request_id, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.STARTED, data=request)


@router.post("/requests/{request_id}/complete", response_model=SuccessResponse[CourierRequestRead])
def complete_my_delivery(
    request_id: UUID,
    db: DbSessionDep,
    settings: SettingsDep,
    current_user: DeliveryTeamMemberDep,
    otp: Annotated[str, Form(pattern=OTP_PATTERN)],
    proof_image: Annotated[UploadFile, File()],
) -> SuccessResponse[CourierRequestRead]:
    DeliveryHandoverService(db, settings.private_upload_dir).complete(
        request_id, otp, proof_image, current_user
    )
    request = CourierRequestService(db).get_for(request_id, current_user)
    return SuccessResponse(message=DeliveryRequestMessages.COMPLETED, data=request)


@router.get("/requests/{request_id}/proof")
def get_my_delivery_proof(
    request_id: UUID, db: DbSessionDep, current_user: DeliveryTeamMemberDep
) -> FileResponse:
    path = DeliveryProofService(db).path_for_courier(request_id, current_user)
    return FileResponse(path, media_type=mimetypes.guess_type(path)[0])
