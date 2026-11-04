from dataclasses import dataclass
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import AccountRoleMessages, RoleUpgradeRequestMessages
from app.core.permissions import (
    ADMIN_ROLE_SLUGS,
    SELECTABLE_ACCOUNT_ROLE_SLUGS,
    VERIFIED_ACCOUNT_ROLE_SLUGS,
    RoleSlug,
)
from app.core.timezone import app_now
from app.models.role import Role
from app.models.role_upgrade_request import RoleUpgradeRequest
from app.models.user import User
from app.realtime.publisher import RealtimePublisher
from app.repositories.role_repository import RoleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account_role import AccountRoleRead, AccountRoleVerificationStatus
from app.services.account_role_status_service import (
    AccountRoleStatusService,
    requires_verification,
)
from app.services.activity_log_service import ActivityLogService
from app.services.role_upgrade_request_service import RoleUpgradeRequestService

_RESUBMITTABLE_STATUSES = frozenset(
    {AccountRoleVerificationStatus.UNVERIFIED, AccountRoleVerificationStatus.REJECTED}
)


@dataclass(frozen=True)
class AccountRoleSelection:
    account_role: AccountRoleRead | None
    request: RoleUpgradeRequest | None


class AccountRoleService:
    def __init__(
        self, db: Session, settings: Settings, publisher: RealtimePublisher | None = None
    ) -> None:
        self._db = db
        self._roles = RoleRepository(db)
        self._users = UserRepository(db)
        self._status = AccountRoleStatusService(db)
        self._requests = RoleUpgradeRequestService(db, settings, publisher)
        self._activity_logs = ActivityLogService(db)

    def list_selectable(self) -> list[Role]:
        return self._roles.list_by_slugs(SELECTABLE_ACCOUNT_ROLE_SLUGS)

    def list_requestable(self, actor: User) -> list[Role]:
        held = {role.id for role in actor.roles}
        return [
            role
            for role in self._roles.list_by_slugs(VERIFIED_ACCOUNT_ROLE_SLUGS)
            if role.id not in held
        ]

    def current(self, user: User) -> AccountRoleRead | None:
        return self._status.describe(user)

    def select(
        self, actor: User, role_id: UUID, document: UploadFile | None = None
    ) -> AccountRoleSelection:
        role = self._selectable_role(role_id)
        if document is not None and not requires_verification(role.slug):
            raise BusinessRuleError(AccountRoleMessages.DOCUMENT_NOT_APPLICABLE)
        self._users.lock(actor)
        self._ensure_can_select(actor)
        previous = [held for held in actor.roles if requires_verification(held.slug)]
        if self._is_current_selection(previous, role):
            if document is not None:
                raise BusinessRuleError(AccountRoleMessages.ROLE_ALREADY_SELECTED)
            return self._confirm_current(actor, role)

        cancelled = self._requests.cancel_pending(actor.id)
        base_role = self._base_role()
        actor.roles = [base_role, role] if requires_verification(role.slug) else [base_role]
        actor.account_role_selected_at = app_now()
        self._db.flush()
        request = (
            self._requests.stage(actor, role, document)
            if requires_verification(role.slug)
            else None
        )
        self._db.commit()

        self._log_selected(actor, role, previous)
        self._requests.log_cancelled(actor, cancelled)
        if request is not None:
            self._requests.announce_submitted(actor, request, role)
        return AccountRoleSelection(account_role=self._status.describe(actor), request=request)

    def submit_verification(
        self, actor: User, document: UploadFile | None = None
    ) -> RoleUpgradeRequest:
        self._users.lock(actor)
        state = self._status.state_for(actor.id)
        if state is None:
            raise BusinessRuleError(AccountRoleMessages.NO_ACCOUNT_ROLE)
        if not state.requires_verification:
            raise BusinessRuleError(AccountRoleMessages.VERIFICATION_NOT_REQUIRED)
        status = state.verification_status
        if status == AccountRoleVerificationStatus.VERIFIED:
            raise BusinessRuleError(AccountRoleMessages.ALREADY_VERIFIED)
        if status not in _RESUBMITTABLE_STATUSES:
            raise BusinessRuleError(RoleUpgradeRequestMessages.DUPLICATE_PENDING_REQUEST)
        request = self._requests.stage(actor, state.role, document)
        self._db.commit()
        self._requests.announce_submitted(actor, request, state.role)
        return request

    def request_role(
        self, actor: User, role_id: UUID, document: UploadFile | None = None
    ) -> RoleUpgradeRequest:
        role = self._roles.get_by_id(role_id)
        if role is None:
            raise BusinessRuleError(RoleUpgradeRequestMessages.UNKNOWN_ROLE)
        if not requires_verification(role.slug):
            raise BusinessRuleError(RoleUpgradeRequestMessages.RESTRICTED_ROLE)
        state = self._status.state_for(actor.id)
        if state is not None and state.role.id == role.id:
            return self.submit_verification(actor, document)
        request = self.select(actor, role.id, document).request
        assert request is not None
        return request

    def _base_role(self) -> Role:
        role = self._roles.get_by_slug(RoleSlug.INDIVIDUAL_USER)
        if role is None:
            raise BusinessRuleError(AccountRoleMessages.NOT_SELECTABLE)
        return role

    def _selectable_role(self, role_id: UUID) -> Role:
        role = self._roles.get_by_id(role_id)
        if role is None or role.slug not in SELECTABLE_ACCOUNT_ROLE_SLUGS:
            raise BusinessRuleError(AccountRoleMessages.NOT_SELECTABLE)
        return role

    @staticmethod
    def _ensure_can_select(actor: User) -> None:
        slugs = {role.slug for role in actor.roles}
        if slugs & ADMIN_ROLE_SLUGS:
            raise BusinessRuleError(AccountRoleMessages.SELECTION_UNAVAILABLE)

    @staticmethod
    def _is_current_selection(previous: list[Role], role: Role) -> bool:
        if requires_verification(role.slug):
            return [held.id for held in previous] == [role.id]
        return not previous

    def _confirm_current(self, actor: User, role: Role) -> AccountRoleSelection:
        first_selection = actor.account_role_selected_at is None
        if first_selection:
            actor.account_role_selected_at = app_now()
        self._db.commit()
        if first_selection:
            self._log_selected(actor, role, [role] if requires_verification(role.slug) else [])
        return AccountRoleSelection(account_role=self._status.describe(actor), request=None)

    def _log_selected(self, actor: User, role: Role, previous: list[Role]) -> None:
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ACCOUNT_ROLE_SELECTED,
            entity_type="user",
            entity_id=actor.id,
            metadata={
                "role_slug": role.slug,
                "previous_role_slugs": [held.slug for held in previous],
            },
        )
