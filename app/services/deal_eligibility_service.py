from uuid import UUID

from sqlalchemy.orm import Session

from app.models.deal import Deal
from app.models.user import User
from app.repositories.deal_invitation_repository import DealInvitationRepository
from app.repositories.user_role_assignment_repository import UserRoleAssignmentRepository
from app.services.deal_settings_service import DealSettingsService


class DealEligibilityService:
    def __init__(self, db: Session) -> None:
        self._settings = DealSettingsService(db)
        self._invitations = DealInvitationRepository(db)
        self._assignments = UserRoleAssignmentRepository(db)

    def accepting_role_ids(self) -> list[UUID]:
        return [role.id for role in self._settings.accepting_roles()]

    def holds_accepting_role(self, user: User) -> bool:
        role_ids = set(self.accepting_role_ids())
        return any(
            assignment.role_id in role_ids and assignment.verified_at is not None
            for assignment in self._assignments.list_for_users([user.id])
        )

    def is_eligible(self, deal: Deal, user: User, role_ids: list[UUID]) -> bool:
        return self._invitations.is_eligible(deal.id, deal.created_by, user.id, role_ids)
