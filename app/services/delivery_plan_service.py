from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import DeliveryMessages
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_settings import DeliverySettings
from app.models.order import DeliveryOption, Order
from app.models.user_address import UserAddress
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.services.delivery_access_service import DeliveryAccessService
from app.services.delivery_schedule import is_within_working_hours, next_working_day
from app.services.delivery_timeout_service import DeliveryTimeoutService


@dataclass(frozen=True)
class DeliveryTarget:
    latitude: float
    longitude: float
    village_id: UUID | None

    @classmethod
    def from_address(cls, address: UserAddress) -> "DeliveryTarget":
        return cls(address.latitude, address.longitude, address.village_id)

    @classmethod
    def from_order(cls, order: Order) -> "DeliveryTarget | None":
        if order.shipping_latitude is None or order.shipping_longitude is None:
            return None
        return cls(order.shipping_latitude, order.shipping_longitude, order.shipping_village_id)


@dataclass(frozen=True)
class EligibleRoute:
    route: DeliveryRoute
    option: DeliveryOption
    fee: Decimal
    delivery_date: date
    window_start: time
    window_end: time


@dataclass(frozen=True)
class DeliveryPlan:
    option: DeliveryOption
    fee: Decimal
    promoter_id: UUID | None = None
    route_id: UUID | None = None
    delivery_date: date | None = None
    window_start: time | None = None
    window_end: time | None = None
    expires_at: datetime | None = None
    notify_promoter_ids: tuple[UUID, ...] = ()


def expected_delivery_fields(plan: DeliveryPlan) -> dict[str, Any]:
    return {
        "expected_delivery_date": plan.delivery_date,
        "expected_delivery_from": plan.window_start,
        "expected_delivery_to": plan.window_end,
    }


def _fee_for(settings: DeliverySettings, option: DeliveryOption) -> Decimal | None:
    return settings.instant_fee if option == DeliveryOption.INSTANT else settings.route_fee


class DeliveryPlanService:
    def __init__(self, db: Session) -> None:
        self._routes = DeliveryRouteRepository(db)
        self._access = DeliveryAccessService(db)
        self._timeouts = DeliveryTimeoutService(db)

    def eligible_routes(
        self,
        option: DeliveryOption,
        target: DeliveryTarget,
        promoter_id: UUID | None,
        now: datetime,
    ) -> list[EligibleRoute]:
        if option == DeliveryOption.SELF_PICKUP:
            return []
        role_ids = [role.id for role in self._access.roles()]
        eligible: list[EligibleRoute] = []
        for route, settings in self._routes.list_serving(
            target.latitude, target.longitude, target.village_id, role_ids, promoter_id
        ):
            fee = _fee_for(settings, option)
            if fee is None:
                continue
            if option == DeliveryOption.INSTANT:
                if not is_within_working_hours(settings, now):
                    continue
                delivery_date = now.date()
            else:
                delivery_date = next_working_day(settings, now.date())
            eligible.append(
                EligibleRoute(
                    route,
                    option,
                    fee,
                    delivery_date,
                    settings.route_start_time,
                    settings.route_end_time,
                )
            )
        return eligible

    def plan(
        self,
        option: DeliveryOption,
        target: DeliveryTarget | None,
        route_id: UUID | None,
        promoter_id: UUID | None,
        now: datetime,
    ) -> DeliveryPlan:
        if option == DeliveryOption.SELF_PICKUP:
            return DeliveryPlan(option=option, fee=Decimal(0))
        if target is None:
            raise BusinessRuleError(DeliveryMessages.ADDRESS_REQUIRED)
        eligible = self.eligible_routes(option, target, promoter_id, now)
        if option == DeliveryOption.ROUTE:
            return self._route_plan(eligible, route_id, now)
        return self._instant_plan(eligible, promoter_id, now)

    def _route_plan(
        self, eligible: list[EligibleRoute], route_id: UUID | None, now: datetime
    ) -> DeliveryPlan:
        if route_id is None:
            raise BusinessRuleError(DeliveryMessages.ROUTE_REQUIRED)
        chosen = next((entry for entry in eligible if entry.route.id == route_id), None)
        if chosen is None:
            raise BusinessRuleError(DeliveryMessages.ROUTE_UNAVAILABLE)
        timeout = self._timeouts.response_window()
        return DeliveryPlan(
            option=chosen.option,
            fee=chosen.fee,
            promoter_id=chosen.route.user_id,
            route_id=chosen.route.id,
            delivery_date=chosen.delivery_date,
            window_start=chosen.window_start,
            window_end=chosen.window_end,
            expires_at=now + timeout,
            notify_promoter_ids=(chosen.route.user_id,),
        )

    def _instant_plan(
        self, eligible: list[EligibleRoute], promoter_id: UUID | None, now: datetime
    ) -> DeliveryPlan:
        if not eligible:
            raise BusinessRuleError(DeliveryMessages.OPTION_UNAVAILABLE)
        timeout = self._timeouts.response_window()
        return DeliveryPlan(
            option=DeliveryOption.INSTANT,
            fee=min(entry.fee for entry in eligible),
            promoter_id=promoter_id,
            delivery_date=now.date(),
            expires_at=now + timeout,
            notify_promoter_ids=tuple(dict.fromkeys(entry.route.user_id for entry in eligible)),
        )
