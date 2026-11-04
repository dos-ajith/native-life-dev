from uuid import UUID

from sqlalchemy.orm import Session

from app.models.order import DeliveryOption
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.schemas.delivery_request import EligibleRouteRead
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_expiry_service import deal_clock_now
from app.services.delivery_plan_service import DeliveryPlanService, DeliveryTarget
from app.services.user_address_service import UserAddressService


class EligibleRouteService:
    def __init__(self, db: Session) -> None:
        self._plans = DeliveryPlanService(db)
        self._addresses = UserAddressService(db)
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._access = DealAccessPolicy(db)

    def list_for(
        self, option: DeliveryOption, address_id: UUID, deal_id: UUID | None, actor: User
    ) -> list[EligibleRouteRead]:
        address = self._addresses.get_owned(address_id, actor)
        promoter_id = self._deal_promoter_id(deal_id, actor)
        eligible = self._plans.eligible_routes(
            option, DeliveryTarget.from_address(address), promoter_id, deal_clock_now()
        )
        return [
            EligibleRouteRead(
                route_id=entry.route.id,
                route_name=entry.route.name,
                promoter_id=entry.route.user_id,
                promoter_name=f"{entry.route.promoter.first_name} {entry.route.promoter.last_name}",
                vehicle_type=entry.route.vehicle.vehicle_type if entry.route.vehicle else None,
                vehicle_name=entry.route.vehicle.name if entry.route.vehicle else None,
                option=entry.option,
                fee=entry.fee,
                delivery_date=entry.delivery_date,
            )
            for entry in eligible
        ]

    def _deal_promoter_id(self, deal_id: UUID | None, actor: User) -> UUID | None:
        if deal_id is None:
            return None
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, actor)
        return self._invitations.accepted_user_id(deal.id)
