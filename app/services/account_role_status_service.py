from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.permissions import VERIFIED_ACCOUNT_ROLE_SLUGS, RoleSlug
from app.models.role import Role
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.models.user import User
from app.models.user_has_role import UserRoleAssignment
from app.repositories.role_upgrade_request_repository import RoleUpgradeRequestRepository
from app.repositories.user_role_assignment_repository import UserRoleAssignmentRepository
from app.schemas.account_role import (
    AccountRoleRead,
    AccountRoleVerificationStatus,
    PublicAccountRoleRead,
)

_REQUEST_STATUS_TO_VERIFICATION = {
    RoleUpgradeRequestStatus.PENDING: AccountRoleVerificationStatus.PENDING,
    RoleUpgradeRequestStatus.REJECTED: AccountRoleVerificationStatus.REJECTED,
}


@dataclass(frozen=True)
class AccountRoleState:
    assignment: UserRoleAssignment
    request: RoleUpgradeRequest | None

    @property
    def role(self) -> Role:
        return self.assignment.role

    @property
    def requires_verification(self) -> bool:
        return requires_verification(self.role.slug)

    @property
    def verification_status(self) -> AccountRoleVerificationStatus:
        return verification_status(
            self.role.slug,
            self.assignment.verified_at is not None,
            self.request.status if self.request is not None else None,
        )


def requires_verification(role_slug: str) -> bool:
    return role_slug in VERIFIED_ACCOUNT_ROLE_SLUGS


def verification_status(
    role_slug: str, is_verified: bool, latest_request_status: RoleUpgradeRequestStatus | None
) -> AccountRoleVerificationStatus:
    if not requires_verification(role_slug):
        return AccountRoleVerificationStatus.NOT_REQUIRED
    if is_verified:
        return AccountRoleVerificationStatus.VERIFIED
    if latest_request_status is None:
        return AccountRoleVerificationStatus.UNVERIFIED
    return _REQUEST_STATUS_TO_VERIFICATION.get(
        latest_request_status, AccountRoleVerificationStatus.UNVERIFIED
    )


def current_account_assignment(
    assignments: Sequence[UserRoleAssignment],
) -> UserRoleAssignment | None:
    selected = [item for item in assignments if requires_verification(item.role.slug)]
    if selected:
        return max(selected, key=lambda item: item.assigned_at)
    return next((item for item in assignments if item.role.slug == RoleSlug.INDIVIDUAL_USER), None)


def latest_applicable_request(
    assignment: UserRoleAssignment, requests: Sequence[RoleUpgradeRequest]
) -> RoleUpgradeRequest | None:
    applicable = [
        request
        for request in requests
        if request.requested_role_id == assignment.role_id
        and request.created_at >= assignment.assigned_at
    ]
    return max(applicable, key=lambda request: request.created_at, default=None)


class AccountRoleStatusService:
    def __init__(self, db: Session) -> None:
        self._assignments = UserRoleAssignmentRepository(db)
        self._requests = RoleUpgradeRequestRepository(db)

    def state_for(self, user_id: UUID) -> AccountRoleState | None:
        return self._states_for([user_id])[user_id]

    def describe(self, user: User) -> AccountRoleRead | None:
        return self.describe_many([user])[user.id]

    def describe_many(self, users: Sequence[User]) -> dict[UUID, AccountRoleRead | None]:
        states = self._states_for([user.id for user in users])
        return {user.id: self._to_read(user, states[user.id]) for user in users}

    def describe_public(self, user_id: UUID) -> PublicAccountRoleRead | None:
        state = self.state_for(user_id)
        if state is None:
            return None
        return PublicAccountRoleRead(
            name=state.role.name,
            slug=state.role.slug,
            requires_verification=state.requires_verification,
            is_verified=state.verification_status == AccountRoleVerificationStatus.VERIFIED,
        )

    def _states_for(self, user_ids: Sequence[UUID]) -> dict[UUID, AccountRoleState | None]:
        assignments_by_user: dict[UUID, list[UserRoleAssignment]] = {
            user_id: [] for user_id in user_ids
        }
        for held in self._assignments.list_for_users(user_ids):
            assignments_by_user[held.user_id].append(held)
        requests_by_user: dict[UUID, list[RoleUpgradeRequest]] = {
            user_id: [] for user_id in user_ids
        }
        for request in self._requests.list_for_users(user_ids):
            requests_by_user[request.user_id].append(request)
        states: dict[UUID, AccountRoleState | None] = {}
        for user_id, assignments in assignments_by_user.items():
            assignment = current_account_assignment(assignments)
            states[user_id] = (
                None
                if assignment is None
                else AccountRoleState(
                    assignment=assignment,
                    request=latest_applicable_request(assignment, requests_by_user[user_id]),
                )
            )
        return states

    @staticmethod
    def _to_read(user: User, state: AccountRoleState | None) -> AccountRoleRead | None:
        if state is None:
            return None
        return AccountRoleRead(
            id=state.role.id,
            name=state.role.name,
            slug=state.role.slug,
            requires_verification=state.requires_verification,
            verification_status=state.verification_status,
            verified_at=state.assignment.verified_at,
            verification_request_id=state.request.id if state.request is not None else None,
            selected_at=user.account_role_selected_at,
            selection_completed=user.account_role_selected_at is not None,
        )
