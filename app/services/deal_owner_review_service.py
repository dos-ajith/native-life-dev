from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import AuthorizationError, ConflictError
from app.core.messages import DealMessages
from app.models.deal import Deal, DealStatus
from app.models.notification import NotificationType
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import DealRead
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, get_deal
from app.services.notification_service import NotificationService

ENTITY_TYPE = "deal"


class DealOwnerReviewService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._deals = DealRepository(db)
        self._access = DealAccessPolicy(db)
        self._notifications = NotificationService(db)
        self._activity_logs = ActivityLogService(db)

    def list_for_my_businesses(
        self, owner: User, status: DealStatus | None, params: PaginationParams
    ) -> tuple[list[DealRead], int]:
        deals, total = self._deals.list_for_business_owner(owner.id, status, params)
        return [DealRead.from_deal(deal, owner) for deal in deals], total

    def block(self, deal_id: UUID, owner: User) -> DealRead:
        deal = self._owned_business_deal(deal_id, owner)
        self._move(deal, DealStatus.PUBLISHED, DealStatus.BLOCKED, DealMessages.NOT_PUBLISHED)
        self._finish(
            deal, owner, deal.created_by, ActivityAction.DEAL_BLOCKED, NotificationType.DEAL_BLOCKED
        )
        return self._read(deal.id, owner)

    def approve_republish(self, deal_id: UUID, owner: User) -> DealRead:
        deal = self._owned_business_deal(deal_id, owner)
        self._move(
            deal,
            DealStatus.PENDING_OWNER_APPROVAL,
            DealStatus.PUBLISHED,
            DealMessages.NOT_AWAITING_OWNER,
        )
        self._finish(
            deal,
            owner,
            deal.created_by,
            ActivityAction.DEAL_REPUBLISH_APPROVED,
            NotificationType.DEAL_REPUBLISH_APPROVED,
        )
        return self._read(deal.id, owner)

    def reject_republish(self, deal_id: UUID, owner: User) -> DealRead:
        deal = self._owned_business_deal(deal_id, owner)
        self._move(
            deal,
            DealStatus.PENDING_OWNER_APPROVAL,
            DealStatus.BLOCKED,
            DealMessages.NOT_AWAITING_OWNER,
        )
        self._finish(
            deal,
            owner,
            deal.created_by,
            ActivityAction.DEAL_REPUBLISH_REJECTED,
            NotificationType.DEAL_REPUBLISH_REJECTED,
        )
        return self._read(deal.id, owner)

    def request_republish(self, deal_id: UUID, creator: User) -> DealRead:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, creator)
        self._move(
            deal, DealStatus.BLOCKED, DealStatus.PENDING_OWNER_APPROVAL, DealMessages.NOT_BLOCKED
        )
        business_owner_id = self._business_owner_id(deal)
        self._finish(
            deal,
            creator,
            business_owner_id,
            ActivityAction.DEAL_REPUBLISH_REQUESTED,
            NotificationType.DEAL_REPUBLISH_REQUESTED,
        )
        return self._read(deal.id, creator)

    def _owned_business_deal(self, deal_id: UUID, owner: User) -> Deal:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_can_view(deal, owner)
        if (
            deal.business is None
            or deal.business.owner_id != owner.id
            or deal.created_by == owner.id
        ):
            raise AuthorizationError(DealMessages.NOT_BUSINESS_OWNER)
        return deal

    @staticmethod
    def _business_owner_id(deal: Deal) -> UUID:
        if deal.business is None:
            raise AuthorizationError(DealMessages.NOT_BUSINESS_OWNER)
        return deal.business.owner_id

    def _move(
        self, deal: Deal, current: DealStatus, target: DealStatus, conflict_message: str
    ) -> None:
        if not self._deals.transition(deal.id, current, target):
            self._db.rollback()
            raise ConflictError(conflict_message)
        self._db.commit()

    def _finish(
        self,
        deal: Deal,
        actor: User,
        recipient_id: UUID,
        action: str,
        notification: NotificationType,
    ) -> None:
        self._activity_logs.log(
            actor=actor, action=action, entity_type=ENTITY_TYPE, entity_id=deal.id
        )
        self._notifications.notify_deal_event(recipient_id, actor, notification, deal.id, deal.name)

    def _read(self, deal_id: UUID, viewer: User) -> DealRead:
        return DealRead.from_deal(get_deal(self._deals, deal_id), viewer)
