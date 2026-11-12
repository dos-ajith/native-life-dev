from uuid import UUID

from sqlalchemy.orm import Session

from app.models.order import DeliveryOption
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.gis_village_repository import GisVillageRepository
from app.schemas.delivery_request import EligibleRouteRead, NearbyRouteRead, NearMissRouteRead
from app.schemas.delivery_route import GeoPoint
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_expiry_service import deal_clock_now
from app.services.delivery_plan_service import (
    DeliveryPlanService,
    DeliveryTarget,
    EligibleRoute,
)
from app.services.route_coverage import coverage_ring
from app.services.user_address_service import UserAddressService


class EligibleRouteService:
    def __init__(self, db: Session) -> None:
        self._plans = DeliveryPlanService(db)
        self._addresses = UserAddressService(db)
        self._deals = DealRepository(db)
        self._villages = GisVillageRepository(db)
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
        return [_eligible_read(entry) for entry in eligible]

    def list_near_misses(
        self, option: DeliveryOption, address_id: UUID, actor: User
    ) -> list[NearMissRouteRead]:
        address = self._addresses.get_owned(address_id, actor)
        misses = self._plans.near_miss_routes(
            option, DeliveryTarget.from_address(address), deal_clock_now()
        )
        return [
            NearMissRouteRead(**_route_fields(entry), meters_outside=meters)
            for entry, meters in misses
        ]

    def list_near(
        self, option: DeliveryOption, latitude: float, longitude: float
    ) -> list[NearbyRouteRead]:
        village = self._villages.find_containing_point(latitude, longitude)
        if village is None:
            return []
        eligible = self._plans.eligible_routes(
            option, DeliveryTarget(latitude, longitude, village.id), None, deal_clock_now()
        )
        return [_nearby_read(entry) for entry in eligible]

    def _deal_promoter_id(self, deal_id: UUID | None, actor: User) -> UUID | None:
        if deal_id is None:
            return None
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, actor)
        return self._invitations.accepted_user_id(deal.id)


def _eligible_read(entry: EligibleRoute) -> EligibleRouteRead:
    return EligibleRouteRead(**_route_fields(entry))


def _nearby_read(entry: EligibleRoute) -> NearbyRouteRead:
    route = entry.route
    return NearbyRouteRead(
        **_route_fields(entry),
        start=GeoPoint(latitude=route.start_latitude, longitude=route.start_longitude),
        end=GeoPoint(latitude=route.end_latitude, longitude=route.end_longitude),
        path=(
            [GeoPoint(latitude=lat, longitude=lng) for lat, lng in route.path_coordinates]
            if route.path_coordinates is not None
            else None
        ),
        coverage_radius_m=route.coverage_radius_m,
        coverage=[
            GeoPoint(latitude=lat, longitude=lng)
            for lat, lng in coverage_ring(
                route.path_coordinates
                or [
                    (route.start_latitude, route.start_longitude),
                    (route.end_latitude, route.end_longitude),
                ],
                route.coverage_radius_m,
            )
        ],
    )


def _route_fields(entry: EligibleRoute) -> dict[str, object]:
    route = entry.route
    return {
        "route_id": route.id,
        "route_name": route.name,
        "promoter_id": route.user_id,
        "promoter_name": f"{route.promoter.first_name} {route.promoter.last_name}",
        "vehicle_type": route.vehicle.vehicle_type if route.vehicle else None,
        "vehicle_name": route.vehicle.name if route.vehicle else None,
        "option": entry.option,
        "fee": entry.fee,
        "delivery_date": entry.delivery_date,
    }
