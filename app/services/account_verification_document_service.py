from collections.abc import Sequence

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import AccountRoleMessages
from app.core.storage import delete_role_upgrade_document
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.models.user import User
from app.repositories.role_upgrade_request_document_repository import (
    RoleUpgradeRequestDocumentRepository,
)
from app.repositories.role_upgrade_request_repository import RoleUpgradeRequestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.account_role import (
    AccountRoleVerificationRead,
    DocumentVerificationStatus,
    VerificationDocumentRead,
    VerificationRoleRead,
    verification_document_file_url,
)
from app.services.account_role_service import AccountRoleService
from app.services.account_role_status_service import AccountRoleState, AccountRoleStatusService
from app.services.activity_log_service import ActivityLogService
from app.services.role_upgrade_request_service import RoleUpgradeRequestService

ENTITY_TYPE = "role_upgrade_request"


def _document_of(request: RoleUpgradeRequest | None) -> VerificationDocumentRead | None:
    if request is None or not request.documents:
        return None
    document = max(request.documents, key=lambda item: item.created_at)
    return VerificationDocumentRead(
        id=document.id,
        request_id=request.id,
        file_name=document.file_name,
        content_type=document.content_type,
        file_size_bytes=document.file_size_bytes,
        file_url=verification_document_file_url(request.id, document.id),
        uploaded_at=document.created_at,
    )


def _first_with_status(
    requests: Sequence[RoleUpgradeRequest], status: RoleUpgradeRequestStatus
) -> RoleUpgradeRequest | None:
    return next((request for request in requests if request.status == status), None)


def describe_rejection(request: RoleUpgradeRequest) -> AccountRoleVerificationRead:
    role = request.requested_role
    assert role is not None
    return AccountRoleVerificationRead(
        role=VerificationRoleRead(id=role.id, name=role.name, slug=role.slug),
        status=DocumentVerificationStatus.REJECTED,
        is_verified=False,
        request_id=request.id,
        review_note=request.review_note,
        document=_document_of(request),
    )


def describe_verification(
    state: AccountRoleState, requests: Sequence[RoleUpgradeRequest]
) -> AccountRoleVerificationRead:
    role = VerificationRoleRead(id=state.role.id, name=state.role.name, slug=state.role.slug)
    is_verified = state.assignment.verified_at is not None
    latest = requests[0] if requests else None
    review_note = (
        latest.review_note
        if latest is not None and latest.status == RoleUpgradeRequestStatus.REJECTED
        else None
    )
    approved = _first_with_status(requests, RoleUpgradeRequestStatus.APPROVED)
    if not state.requires_verification:
        status, source = DocumentVerificationStatus.NOT_REQUIRED, None
    elif latest is not None and latest.status == RoleUpgradeRequestStatus.PENDING:
        if latest.documents:
            status, source = DocumentVerificationStatus.UNDER_REVIEW, latest
        else:
            status, source = DocumentVerificationStatus.DOCUMENT_REQUIRED, approved
    elif is_verified:
        status, source = DocumentVerificationStatus.VERIFIED, approved
    elif latest is not None and latest.status == RoleUpgradeRequestStatus.REJECTED:
        status, source = DocumentVerificationStatus.REJECTED, latest
    else:
        status, source = DocumentVerificationStatus.DOCUMENT_REQUIRED, None
    return AccountRoleVerificationRead(
        role=role,
        status=status,
        is_verified=is_verified,
        request_id=latest.id if latest is not None else None,
        review_note=review_note,
        document=_document_of(source),
    )


class AccountVerificationDocumentService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._status = AccountRoleStatusService(db)
        self._requests = RoleUpgradeRequestRepository(db)
        self._documents = RoleUpgradeRequestDocumentRepository(db)
        self._users = UserRepository(db)
        self._upgrades = RoleUpgradeRequestService(db, settings)
        self._account_roles = AccountRoleService(db, settings)
        self._activity_logs = ActivityLogService(db)

    def overview(self, user: User) -> AccountRoleVerificationRead:
        state = self._status.state_for(user.id)
        if state is None:
            return AccountRoleVerificationRead(
                role=None,
                status=DocumentVerificationStatus.NOT_REQUIRED,
                is_verified=False,
                request_id=None,
                review_note=None,
                document=None,
            )
        if not state.requires_verification:
            rejection = self._unanswered_rejection(user)
            if rejection is not None:
                return describe_rejection(rejection)
        return describe_verification(state, self._applicable_requests(user, state))

    def replace_document(self, user: User, document: UploadFile) -> AccountRoleVerificationRead:
        self._users.lock(user)
        state = self._status.state_for(user.id)
        if state is None:
            raise BusinessRuleError(AccountRoleMessages.NO_ACCOUNT_ROLE)
        if not state.requires_verification:
            self._reapply_after_rejection(user, document)
            self._db.expire_all()
            return self.overview(user)
        requests = self._applicable_requests(user, state)
        latest = requests[0] if requests else None
        if latest is not None and latest.status == RoleUpgradeRequestStatus.PENDING:
            self._replace_on_pending(user, latest, document)
        else:
            request = self._upgrades.stage(user, state.role, document)
            self._db.commit()
            self._upgrades.announce_submitted(user, request, state.role)
        self._db.expire_all()
        return self.overview(user)

    def _reapply_after_rejection(self, user: User, document: UploadFile) -> None:
        rejection = self._unanswered_rejection(user)
        if rejection is None or rejection.requested_role_id is None:
            raise BusinessRuleError(AccountRoleMessages.VERIFICATION_NOT_REQUIRED)
        self._account_roles.select(user, rejection.requested_role_id, document)

    def _unanswered_rejection(self, user: User) -> RoleUpgradeRequest | None:
        latest = next(
            (
                request
                for request in self._requests.list_for_users([user.id])
                if request.status != RoleUpgradeRequestStatus.CANCELLED
            ),
            None,
        )
        if latest is None or latest.status != RoleUpgradeRequestStatus.REJECTED:
            return None
        if latest.requested_role is None or latest.reviewed_at is None:
            return None
        selected_at = user.account_role_selected_at
        if selected_at is not None and selected_at > latest.reviewed_at:
            return None
        return latest

    def _replace_on_pending(
        self, user: User, request: RoleUpgradeRequest, document: UploadFile
    ) -> None:
        replaced_paths = self._documents.delete_for_request(request.id)
        saved = self._documents.stage(self._upgrades.store_document(request, document))
        self._db.commit()
        for path in replaced_paths:
            delete_role_upgrade_document(path)
        self._activity_logs.log(
            actor=user,
            action=ActivityAction.ROLE_UPGRADE_DOCUMENT_REPLACED,
            entity_type=ENTITY_TYPE,
            entity_id=request.id,
            metadata={"document_id": str(saved.id), "replaced_count": len(replaced_paths)},
        )

    def _applicable_requests(self, user: User, state: AccountRoleState) -> list[RoleUpgradeRequest]:
        return [
            request
            for request in self._requests.list_for_users([user.id])
            if request.requested_role_id == state.assignment.role_id
            and request.created_at >= state.assignment.assigned_at
            and request.status != RoleUpgradeRequestStatus.CANCELLED
        ]
