from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError
from app.core.messages import DealMessages
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.deal import DealRead
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, get_deal

ENTITY_TYPE = "deal"


class DealUnpublishService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._participants = DealParticipantRepository(db)
        self._orders = OrderRepository(db)
        self._access = DealAccessPolicy(db)
        self._activity_logs = ActivityLogService(db)

    def unpublish(self, deal_id: UUID, actor: User) -> DealRead:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_unpublish(deal, actor)
        if self._orders.deal_has_open_orders(deal.id):
            raise ConflictError(DealMessages.HAS_OPEN_ORDERS)
        if not self._deals.unpublish(deal.id):
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_UNPUBLISHABLE)
        removed_participants = self._participants.delete_for_deal(deal.id)
        self._invitations.delete_for_deal(deal.id)
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DEAL_UNPUBLISHED,
            entity_type=ENTITY_TYPE,
            entity_id=deal.id,
            metadata={
                "removed_participants": removed_participants,
                "by_owner": deal.created_by == actor.id,
            },
        )
        return DealRead.from_deal(get_deal(self._deals, deal.id), actor)
