from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.messages import DealMessages
from app.core.permissions import PermissionName
from app.models.deal import Deal, DealStatus
from app.models.deal_invitation import DealInvitationStatus
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.services.authorization_service import has_permission
from app.services.deal_eligibility_service import DealEligibilityService
from app.services.deal_expiry_service import deal_clock_now


def get_deal(deals: DealRepository, deal_id: UUID) -> Deal:
    deal = deals.get_by_id(deal_id)
    if deal is None:
        raise NotFoundError(DealMessages.NOT_FOUND)
    return deal


def ensure_draft(deal: Deal) -> None:
    if deal.status != DealStatus.DRAFT:
        raise ConflictError(DealMessages.NOT_DRAFT)


class DealAccessPolicy:
    def __init__(self, db: Session) -> None:
        self._deals = DealRepository(db)
        self._invitations = DealInvitationRepository(db)
        self._places = UserNativePlaceRepository(db)
        self._eligibility = DealEligibilityService(db)

    def ensure_can_view(self, deal: Deal, viewer: User) -> None:
        if not self.can_view(deal, viewer):
            raise NotFoundError(DealMessages.NOT_FOUND)

    def ensure_owner(self, deal: Deal, actor: User) -> None:
        if deal.created_by == actor.id:
            return
        if self.can_view(deal, actor):
            raise AuthorizationError(DealMessages.NOT_OWNER)
        raise NotFoundError(DealMessages.NOT_FOUND)

    def ensure_can_list_participants(self, deal: Deal, actor: User) -> None:
        if deal.created_by == actor.id or has_permission(actor, PermissionName.DEAL_VIEW_ANY):
            return
        if self.can_view(deal, actor):
            raise AuthorizationError(DealMessages.NOT_OWNER)
        raise NotFoundError(DealMessages.NOT_FOUND)

    def ensure_not_publisher(self, deal: Deal, actor: User) -> None:
        if deal.created_by == actor.id:
            raise AuthorizationError(DealMessages.CANNOT_JOIN_OWN)
        if deal.business is not None and deal.business.owner_id == actor.id:
            raise AuthorizationError(DealMessages.CANNOT_JOIN_OWN)
        invitation = self._invitations.get_for_user(deal.id, actor.id)
        if invitation is not None and invitation.status == DealInvitationStatus.ACCEPTED:
            raise AuthorizationError(DealMessages.CANNOT_JOIN_ACCEPTED)

    def can_view(self, deal: Deal, viewer: User) -> bool:
        if deal.created_by == viewer.id or has_permission(viewer, PermissionName.DEAL_VIEW_ANY):
            return True
        if deal.business is not None and deal.business.owner_id == viewer.id:
            return True
        if self._is_participating_invitee(deal, viewer):
            return True
        village_ids = [place.village_id for place in self._places.list_hierarchy(viewer.id)]
        return self._deals.is_published_visible_in(deal.id, village_ids, deal_clock_now())

    def _is_participating_invitee(self, deal: Deal, viewer: User) -> bool:
        invitation = self._invitations.get_for_user(deal.id, viewer.id)
        if invitation is None:
            return False
        if invitation.status == DealInvitationStatus.ACCEPTED:
            return True
        if invitation.status != DealInvitationStatus.INVITED:
            return False
        if deal.status != DealStatus.PENDING_ACCEPTANCE:
            return False
        try:
            role_ids = self._eligibility.accepting_role_ids()
        except ServiceUnavailableError:
            return False
        return self._eligibility.is_eligible(deal, viewer, role_ids)
