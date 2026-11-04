from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from app.core.messages import DealMessages
from app.models.deal import Deal, DealStatus
from app.models.deal_invitation import DealInvitation, DealInvitationStatus
from app.models.user import User
from app.realtime.publisher import RealtimePublisher
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import DealInvitationRead, DealRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import get_deal
from app.services.deal_eligibility_service import DealEligibilityService
from app.services.deal_expiry_service import DealExpiryService, deal_clock_now
from app.services.notification_service import NotificationService

ENTITY_TYPE = "deal"


class DealAcceptanceService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._eligibility = DealEligibilityService(db)
        self._expiry = DealExpiryService(db, publisher)
        self._notifications = NotificationService(db, publisher)
        self._activity_logs = ActivityLogService(db)

    def list_open(
        self, viewer: User, params: PaginationParams
    ) -> tuple[list[DealInvitationRead], int]:
        self._expiry.expire_overdue()
        role_ids = self._eligibility.accepting_role_ids()
        invitations, total = self._invitations.list_open_for_user(
            viewer.id, role_ids, deal_clock_now(), params
        )
        deals = self._deals.get_by_ids([invitation.deal_id for invitation in invitations])
        return [
            DealInvitationRead.from_invitation(invitation, deals[invitation.deal_id], viewer)
            for invitation in invitations
        ], total

    def accept(self, deal_id: UUID, viewer: User) -> DealRead:
        deal = self._open_deal_for(deal_id, viewer)
        now = deal_clock_now()
        status = self._deals.record_acceptance(deal.id, now)
        if status is None:
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_PENDING)
        if not self._invitations.accept(deal.id, viewer.id, now):
            self._db.rollback()
            raise ConflictError(DealMessages.INVITATION_CLOSED)
        published = status == DealStatus.PUBLISHED
        if published:
            self._invitations.close_open([deal.id])
        self._db.commit()
        self._log(viewer, ActivityAction.DEAL_ACCEPTED, deal.id)
        if published:
            self._log(viewer, ActivityAction.DEAL_PUBLISHED, deal.id)
            self._notifications.notify_deal_published(deal.created_by, viewer, deal.id, deal.name)
        return DealRead.from_deal(get_deal(self._deals, deal.id), viewer)

    def decline(self, deal_id: UUID, viewer: User) -> None:
        deal = self._open_deal_for(deal_id, viewer)
        if not self._invitations.decline(deal.id, viewer.id, deal_clock_now()):
            self._db.rollback()
            raise ConflictError(DealMessages.INVITATION_CLOSED)
        self._db.commit()
        self._log(viewer, ActivityAction.DEAL_DECLINED, deal.id)

    def _open_deal_for(self, deal_id: UUID, viewer: User) -> Deal:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        invitation = self._invitations.get_for_user(deal.id, viewer.id)
        if invitation is None:
            raise NotFoundError(DealMessages.INVITATION_NOT_FOUND)
        self._ensure_open(deal, invitation)
        role_ids = self._eligibility.accepting_role_ids()
        if not self._eligibility.is_eligible(deal, viewer, role_ids):
            raise AuthorizationError(DealMessages.NOT_ELIGIBLE)
        return deal

    @staticmethod
    def _ensure_open(deal: Deal, invitation: DealInvitation) -> None:
        if invitation.status != DealInvitationStatus.INVITED:
            raise ConflictError(DealMessages.INVITATION_CLOSED)
        if deal.status != DealStatus.PENDING_ACCEPTANCE:
            raise ConflictError(DealMessages.NOT_PENDING)

    def _log(self, actor: User, action: str, deal_id: UUID) -> None:
        self._activity_logs.log(
            actor=actor, action=action, entity_type=ENTITY_TYPE, entity_id=deal_id
        )
