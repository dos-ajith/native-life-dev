from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError, NotFoundError
from app.core.messages import DealMessages
from app.models.deal_participant import DealParticipant
from app.models.user import User
from app.repositories.cart_repository import CartRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.deal import DealRead
from app.schemas.deal_participant import DealParticipantRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.deal_availability import ensure_deal_open
from app.services.deal_expiry_service import DealExpiryService

ENTITY_TYPE = "deal"


class DealParticipationService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._participants = DealParticipantRepository(db)
        self._orders = OrderRepository(db)
        self._carts = CartRepository(db)
        self._access = DealAccessPolicy(db)
        self._expiry = DealExpiryService(db)
        self._activity_logs = ActivityLogService(db)

    def join(self, deal_id: UUID, actor: User) -> DealRead:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, actor)
        self._access.ensure_not_publisher(deal, actor)
        ensure_deal_open(deal)
        if self._participants.exists(deal.id, actor.id):
            raise ConflictError(DealMessages.ALREADY_JOINED)
        try:
            self._participants.add(DealParticipant(deal_id=deal.id, user_id=actor.id))
            self._deals.adjust_joined_count(deal.id, 1)
            self._db.commit()
        except IntegrityError as exc:
            self._db.rollback()
            raise ConflictError(DealMessages.ALREADY_JOINED) from exc
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DEAL_JOINED,
            entity_type=ENTITY_TYPE,
            entity_id=deal.id,
        )
        return DealRead.from_deal(get_deal(self._deals, deal.id), actor, has_joined=True)

    def leave(self, deal_id: UUID, actor: User) -> None:
        deal = get_deal(self._deals, deal_id)
        if not self._participants.exists(deal.id, actor.id):
            raise NotFoundError(DealMessages.NOT_JOINED)
        if self._orders.customer_has_open_order_in_deal(actor.id, deal.id):
            raise ConflictError(DealMessages.LEAVE_BLOCKED_BY_ORDERS)
        self._participants.delete(deal.id, actor.id)
        self._deals.adjust_joined_count(deal.id, -1)
        self._carts.remove_for_deal(actor.id, deal.id)
        self._db.commit()
        self._activity_logs.log(
            actor=actor, action=ActivityAction.DEAL_LEFT, entity_type=ENTITY_TYPE, entity_id=deal.id
        )

    def list_participants(
        self, deal_id: UUID, actor: User, params: PaginationParams
    ) -> tuple[list[DealParticipantRead], int]:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_list_participants(deal, actor)
        rows, total = self._participants.list_for_deal(deal.id, params)
        return [
            DealParticipantRead.from_participant(participant, order_count)
            for participant, order_count in rows
        ], total

    def list_joined(self, actor: User, params: PaginationParams) -> tuple[list[DealRead], int]:
        self._expiry.expire_overdue()
        deals, total = self._deals.list_joined_by(actor.id, params)
        return [DealRead.from_deal(deal, actor, has_joined=True) for deal in deals], total
