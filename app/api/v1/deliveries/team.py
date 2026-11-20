from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import ActivityRequestMetaDep, DbSessionDep, require_permission
from app.api.v1.deliveries.permissions import VerifiedPromoterDep
from app.core.messages import DeliveryTeamMessages, DeliveryVehicleMessages
from app.core.openapi_tags import ApiTag
from app.core.permissions import PermissionName
from app.models.user import User
from app.schemas.delivery_team import (
    DeliveryTeamMemberCreate,
    DeliveryTeamMemberRead,
    PromoterOptionRead,
)
from app.schemas.delivery_vehicle import TeamVehicleRead
from app.schemas.response import SuccessResponse
from app.services.delivery_team_service import DeliveryTeamService
from app.services.delivery_vehicle_service import DeliveryVehicleService

router = APIRouter(prefix="/delivery-team", tags=[ApiTag.DELIVERY_TEAM])

TeamCreatorDep = Annotated[User, Depends(require_permission(PermissionName.DELIVERY_TEAM_CREATE))]
TeamViewerDep = Annotated[User, Depends(require_permission(PermissionName.DELIVERY_TEAM_VIEW_OWN))]
PromoterSelectorDep = Annotated[
    User, Depends(require_permission(PermissionName.DELIVERY_TEAM_SELECT_PROMOTER))
]


@router.post(
    "", response_model=SuccessResponse[DeliveryTeamMemberRead], status_code=status.HTTP_201_CREATED
)
def create_team_member(
    payload: DeliveryTeamMemberCreate,
    db: DbSessionDep,
    current_user: TeamCreatorDep,
    meta: ActivityRequestMetaDep,
) -> SuccessResponse[DeliveryTeamMemberRead]:
    member = DeliveryTeamService(db).create(payload, current_user, meta.ip_address, meta.user_agent)
    return SuccessResponse(
        message=DeliveryTeamMessages.CREATED, data=DeliveryTeamMemberRead.model_validate(member)
    )


@router.get("", response_model=SuccessResponse[list[DeliveryTeamMemberRead]])
def list_my_team(
    db: DbSessionDep, current_user: TeamViewerDep
) -> SuccessResponse[list[DeliveryTeamMemberRead]]:
    members = DeliveryTeamService(db).list_team(current_user)
    return SuccessResponse(
        message=DeliveryTeamMessages.LIST_RETRIEVED,
        data=[DeliveryTeamMemberRead.model_validate(member) for member in members],
    )


@router.get("/promoters", response_model=SuccessResponse[list[PromoterOptionRead]])
def list_promoters(
    db: DbSessionDep, _: PromoterSelectorDep
) -> SuccessResponse[list[PromoterOptionRead]]:
    promoters = DeliveryTeamService(db).list_promoters()
    return SuccessResponse(
        message=DeliveryTeamMessages.PROMOTERS_RETRIEVED,
        data=[PromoterOptionRead.model_validate(promoter) for promoter in promoters],
    )


@router.get("/vehicles", response_model=SuccessResponse[list[TeamVehicleRead]])
def list_team_vehicles(
    db: DbSessionDep, current_user: VerifiedPromoterDep
) -> SuccessResponse[list[TeamVehicleRead]]:
    return SuccessResponse(
        message=DeliveryVehicleMessages.TEAM_LIST_RETRIEVED,
        data=DeliveryVehicleService(db).list_for_team(current_user),
    )
