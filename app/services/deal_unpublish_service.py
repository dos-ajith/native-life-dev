from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError
from app.core.messages import DealMessages
from app.models.deal import DealStatus
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_participant_repository import DealParticipantRepository
from app.repositories.deal_repository import DealRepository
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
        self._access = DealAccessPolicy(db)
        self._activity_logs = ActivityLogService(db)

    def unpublish(self, deal_id: UUID, actor: User) -> DealRead:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_unpublish(deal, actor)
        if deal.status != DealStatus.PUBLISHED:
            raise ConflictError(DealMessages.NOT_UNPUBLISHABLE)
        if not self._deals.unpublish(deal.id):
            self._db.rollback()
            raise ConflictError(self._refusal_message(deal.id))
        self._invitations.delete_for_deal(deal.id)
        self._db.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DEAL_UNPUBLISHED,
            entity_type=ENTITY_TYPE,
            entity_id=deal.id,
            metadata={"by_owner": deal.created_by == actor.id},
        )
        return DealRead.from_deal(get_deal(self._deals, deal.id), actor)

    def _refusal_message(self, deal_id: UUID) -> str:
        if self._participants.exists_for_deal(deal_id):
            return DealMessages.HAS_PARTICIPANTS
        return DealMessages.NOT_UNPUBLISHABLE
