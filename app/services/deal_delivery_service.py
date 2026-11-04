from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import DeliveryMessages
from app.models.deal import Deal
from app.models.delivery_settings import DeliverySettings
from app.models.order import DeliveryOption
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.delivery_settings_repository import (
    DeliverySettingsRepository,
)
from app.schemas.delivery import DeliveryOptionRead
from app.services.delivery_plan_service import DeliveryPlan, DeliveryPlanService, DeliveryTarget
from app.services.delivery_schedule import is_within_working_hours


def _promoter_option(
    option: DeliveryOption, fee: Decimal, available: bool, settings: DeliverySettings
) -> DeliveryOptionRead:
    return DeliveryOptionRead(
        option=option,
        fee=fee,
        available=available,
        working_days=list(settings.working_days),
        window_start=settings.route_start_time,
        window_end=settings.route_end_time,
    )


class DealDeliveryService:
    def __init__(self, db: Session) -> None:
        self._invitations = DealInvitationRepository(db)
        self._settings = DeliverySettingsRepository(db)
        self._plans = DeliveryPlanService(db)

    def options_for(self, deal: Deal, now: datetime) -> list[DeliveryOptionRead]:
        options: list[DeliveryOptionRead] = []
        settings = self._promoter_settings(deal)
        if settings is not None and settings.instant_fee is not None:
            options.append(
                _promoter_option(
                    DeliveryOption.INSTANT,
                    settings.instant_fee,
                    is_within_working_hours(settings, now),
                    settings,
                )
            )
        if settings is not None and settings.route_fee is not None:
            options.append(
                _promoter_option(DeliveryOption.ROUTE, settings.route_fee, True, settings)
            )
        if deal.pickup_location is not None:
            options.append(
                DeliveryOptionRead(
                    option=DeliveryOption.SELF_PICKUP,
                    fee=Decimal(0),
                    available=True,
                    working_days=[],
                    window_start=None,
                    window_end=None,
                )
            )
        return options

    def accepted_promoter_id(self, deal: Deal) -> UUID | None:
        return self._invitations.accepted_user_id(deal.id)

    def quote(
        self,
        deal: Deal,
        option: DeliveryOption,
        target: DeliveryTarget | None,
        route_id: UUID | None,
        now: datetime,
    ) -> DeliveryPlan:
        chosen = next(
            (entry for entry in self.options_for(deal, now) if entry.option == option), None
        )
        if chosen is None or not chosen.available:
            raise BusinessRuleError(DeliveryMessages.OPTION_UNAVAILABLE)
        return self._plans.plan(option, target, route_id, self.accepted_promoter_id(deal), now)

    def _promoter_settings(self, deal: Deal) -> DeliverySettings | None:
        promoter_id = self.accepted_promoter_id(deal)
        return self._settings.get_by_user(promoter_id) if promoter_id is not None else None
