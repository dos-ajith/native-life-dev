from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.messages import DealMessages
from app.models.deal import Deal, DealStatus
from app.models.notification import NotificationType
from app.models.user import User
from app.plugins.registry import PluginRegistry
from app.realtime.publisher import RealtimePublisher
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import DealRead
from app.services.activity_log_service import ActivityLogService
from app.services.deal_access_policy import DealAccessPolicy, ensure_draft, get_deal
from app.services.deal_eligibility_service import DealEligibilityService
from app.services.deal_expiry_service import DealExpiryService, deal_clock_now
from app.services.deal_product_item_service import DealProductItemService
from app.services.deal_service import DealContentValidator
from app.services.deal_settings_service import DealSettingsService
from app.services.notification_service import NotificationService

ENTITY_TYPE = "deal"
DEAL_MAX_ACCEPTANCES = 1


@dataclass(frozen=True)
class DealSubmissionResult:
    deal: DealRead
    invited_count: int


class DealSubmissionService:
    def __init__(
        self,
        db: Session,
        publisher: RealtimePublisher | None = None,
        registry: PluginRegistry | None = None,
    ) -> None:
        self._db = db
        self._product_items = DealProductItemService(db, registry)
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._content = DealContentValidator(db)
        self._access = DealAccessPolicy(db)
        self._settings = DealSettingsService(db)
        self._eligibility = DealEligibilityService(db)
        self._expiry = DealExpiryService(db, publisher)
        self._notifications = NotificationService(db, publisher)
        self._activity_logs = ActivityLogService(db)

    def submit(self, deal_id: UUID, actor: User) -> DealSubmissionResult:
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        ensure_draft(deal)
        village_id = self._ensure_ready(deal, actor)
        role_ids = self._eligibility.accepting_role_ids()
        timeout = self._settings.acceptance_timeout()
        now = deal_clock_now()
        if not self._deals.mark_submitted(deal.id, now, now + timeout, DEAL_MAX_ACCEPTANCES):
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_DRAFT)
        self._deals.set_primary_village(deal.id, village_id)
        own_role_id = self._eligibility.verified_accepting_role_id(actor)
        if own_role_id is not None:
            return self._publish_by_creator(deal, actor, own_role_id, village_id, now)
        invited = self._invitations.invite_eligible(deal.id, deal.created_by, role_ids)
        self._db.commit()
        self._log(
            actor,
            ActivityAction.DEAL_SUBMITTED,
            deal.id,
            {"invited_count": len(invited), "village_id": str(village_id)},
        )
        self._notify_open_invitations(deal.id, deal.name, actor)
        if not invited:
            self._notifications.notify_deal_no_eligible_acceptors(actor.id, deal.id, deal.name)
            self._notifications.notify_admins_deal_no_eligible_acceptors(actor, deal.id, deal.name)
        return self._result(deal.id, actor, len(invited))

    def _publish_by_creator(
        self, deal: Deal, actor: User, role_id: UUID, village_id: UUID, now: datetime
    ) -> DealSubmissionResult:
        if self._deals.record_acceptance(deal.id, now) is None:
            self._db.rollback()
            raise ConflictError(DealMessages.NOT_PENDING)
        self._invitations.add_accepted(deal.id, actor.id, role_id, now)
        self._db.commit()
        metadata: dict[str, object] = {"invited_count": 0, "village_id": str(village_id)}
        self._log(actor, ActivityAction.DEAL_SUBMITTED, deal.id, metadata)
        self._log(actor, ActivityAction.DEAL_ACCEPTED, deal.id, {"self_accepted": True})
        self._log(actor, ActivityAction.DEAL_PUBLISHED, deal.id, {"self_accepted": True})
        self._notify_business_owner(deal, actor)
        return self._result(deal.id, actor, 0)

    def _notify_business_owner(self, deal: Deal, actor: User) -> None:
        if deal.business is not None and deal.business.owner_id != actor.id:
            self._notifications.notify_deal_event(
                deal.business.owner_id,
                actor,
                NotificationType.DEAL_PROMOTED_FOR_BUSINESS,
                deal.id,
                deal.name,
            )

    def refresh_invitations(self, deal_id: UUID, actor: User) -> DealSubmissionResult:
        self._expiry.expire_overdue()
        deal = get_deal(self._deals, deal_id)
        self._access.ensure_owner(deal, actor)
        if deal.status != DealStatus.PENDING_ACCEPTANCE:
            raise ConflictError(DealMessages.NOT_PENDING)
        role_ids = self._eligibility.accepting_role_ids()
        invited = self._invitations.invite_eligible(deal.id, deal.created_by, role_ids)
        self._db.commit()
        self._log(
            actor,
            ActivityAction.DEAL_INVITATIONS_REFRESHED,
            deal.id,
            {"invited_count": len(invited)},
        )
        self._notify_open_invitations(deal.id, deal.name, actor)
        return self._result(deal.id, actor, len(invited))

    def _ensure_ready(self, deal: Deal, actor: User) -> UUID:
        if not deal.items:
            raise BusinessRuleError(DealMessages.ITEMS_REQUIRED)
        if not any(image.is_thumbnail for image in deal.images):
            raise BusinessRuleError(DealMessages.THUMBNAIL_REQUIRED)
        if deal.valid_until is not None and deal.valid_until <= deal_clock_now():
            raise BusinessRuleError(DealMessages.VALID_UNTIL_IN_PAST)
        self._content.ensure_category(deal.category_id)
        if deal.business_id is not None:
            self._content.ensure_can_promote_business(deal.business_id, actor)
            self._product_items.ensure_ready(deal)
        return self._content.primary_village_id(actor)

    def _notify_open_invitations(self, deal_id: UUID, deal_name: str, creator: User) -> None:
        for invitation in self._invitations.list_unnotified(deal_id):
            if self._invitations.claim_for_notification(invitation.id, deal_clock_now()):
                self._notifications.notify_deal_acceptance_requested(
                    invitation.user_id, creator, deal_id, deal_name
                )

    def _result(self, deal_id: UUID, actor: User, invited_count: int) -> DealSubmissionResult:
        return DealSubmissionResult(
            deal=DealRead.from_deal(get_deal(self._deals, deal_id), actor),
            invited_count=invited_count,
        )

    def _log(self, actor: User, action: str, deal_id: UUID, metadata: dict[str, object]) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=deal_id,
            metadata=metadata,
        )
