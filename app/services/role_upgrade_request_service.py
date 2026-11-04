import logging
from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email_templates import (
    render_role_upgrade_approved_email,
    render_role_upgrade_rejected_email,
)
from app.core.exceptions import AuthorizationError, BusinessRuleError, NotFoundError
from app.core.messages import RoleUpgradeRequestMessages
from app.core.permissions import PROMOTER_REVIEW_ROLE_SLUGS, PermissionName, RoleSlug
from app.core.storage import save_role_upgrade_document
from app.core.timezone import app_now
from app.models.email import EmailType
from app.models.role import Role
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.models.role_upgrade_request_document import RoleUpgradeRequestDocument
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.role_upgrade_request_document_repository import (
    RoleUpgradeRequestDocumentRepository,
)
from app.repositories.role_upgrade_request_repository import RoleUpgradeRequestRepository
from app.repositories.user_role_assignment_repository import UserRoleAssignmentRepository
from app.schemas.pagination import PaginationParams
from app.schemas.role import RoleSummary
from app.schemas.user import UserSummaryRead
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.community_service import CommunityService
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService

logger = logging.getLogger("app.role_upgrade")


class RoleUpgradeRequestService:
    def __init__(
        self, db: Session, settings: Settings, publisher: RealtimePublisher | None = None
    ) -> None:
        self._publisher = publisher or get_realtime_publisher()
        self._db = db
        self._settings = settings
        self._requests = RoleUpgradeRequestRepository(db)
        self._documents = RoleUpgradeRequestDocumentRepository(db)
        self._assignments = UserRoleAssignmentRepository(db)
        self._users = UserService(db)
        self._communities = CommunityService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db, self._publisher)
        self._emails = EmailService(db, settings)

    def stage(self, actor: User, role: Role, document: UploadFile | None) -> RoleUpgradeRequest:
        request = self._requests.stage_pending(actor.id, role.id)
        if request is None:
            raise BusinessRuleError(RoleUpgradeRequestMessages.DUPLICATE_PENDING_REQUEST)
        if document is not None:
            self._documents.stage(self._store_document(request, document))
        return request

    def cancel_pending(self, user_id: UUID) -> list[RoleUpgradeRequest]:
        return self._requests.cancel_pending_for_user(user_id)

    def announce_submitted(self, actor: User, request: RoleUpgradeRequest, role: Role) -> None:
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ROLE_UPGRADE_REQUESTED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"requested_role_id": str(role.id), "role_name": role.name},
        )
        reviewers = self._notifications.notify_role_upgrade_requested(
            actor=actor, request_id=request.id, role_name=role.name, role_slug=role.slug
        )
        self._publish_request_created(request, role, actor, reviewers)

    def log_cancelled(self, actor: User, requests: list[RoleUpgradeRequest]) -> None:
        for request in requests:
            self._activity_logs.log(
                actor=actor,
                action=ActivityAction.ROLE_UPGRADE_CANCELLED,
                entity_type="role_upgrade_request",
                entity_id=request.id,
                metadata={"role_id": str(request.requested_role_id)},
            )

    def add_document(
        self, actor: User, request_id: UUID, document: UploadFile
    ) -> RoleUpgradeRequestDocument:
        request = self._requests.get_by_id_for_user(request_id, actor.id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        if request.status != RoleUpgradeRequestStatus.PENDING:
            raise BusinessRuleError(RoleUpgradeRequestMessages.REQUEST_NOT_PENDING)

        doc = self._documents.add(self._store_document(request, document))
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ROLE_UPGRADE_DOCUMENT_ADDED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"document_id": str(doc.id)},
        )
        return doc

    def _store_document(
        self, request: RoleUpgradeRequest, document: UploadFile
    ) -> RoleUpgradeRequestDocument:
        storage_path, content_type, size_bytes = save_role_upgrade_document(
            document, self._settings.private_upload_dir
        )
        return RoleUpgradeRequestDocument(
            request_id=request.id,
            file_name=document.filename or "document",
            content_type=content_type,
            file_size_bytes=size_bytes,
            storage_path=storage_path,
        )

    def get_own(self, actor: User, request_id: UUID) -> RoleUpgradeRequest:
        request = self._requests.get_by_id_for_user(request_id, actor.id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        return request

    def list_own(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[RoleUpgradeRequest], int]:
        return self._requests.list_by_user(actor.id, params)

    def get_for_admin(self, request_id: UUID, reviewer: User) -> RoleUpgradeRequest:
        request = self._requests.get_by_id(request_id)
        if request is None or not self._can_review(
            reviewer, request, PermissionName.ROLE_UPGRADE_REQUEST_VIEW_ANY
        ):
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        return request

    def list_pending(
        self, params: PaginationParams, reviewer: User
    ) -> tuple[list[RoleUpgradeRequest], int]:
        if has_permission(reviewer, PermissionName.ROLE_UPGRADE_REQUEST_VIEW_ANY):
            return self._requests.list_pending(params)
        return self._requests.list_pending(params, PROMOTER_REVIEW_ROLE_SLUGS)

    def get_document_for_download(
        self, actor: User, request_id: UUID, document_id: UUID
    ) -> RoleUpgradeRequestDocument:
        document = self._documents.get_by_id(document_id)
        if document is None or document.request_id != request_id:
            raise NotFoundError(RoleUpgradeRequestMessages.DOCUMENT_NOT_FOUND)
        request = self._requests.get_by_id(document.request_id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.DOCUMENT_NOT_FOUND)
        if request.user_id != actor.id and not self._can_review(
            actor, request, PermissionName.ROLE_UPGRADE_REQUEST_VIEW_ANY
        ):
            raise NotFoundError(RoleUpgradeRequestMessages.DOCUMENT_NOT_FOUND)
        return document

    def approve(
        self,
        request_id: UUID,
        admin: User,
        review_note: str | None,
        background_tasks: BackgroundTasks,
    ) -> RoleUpgradeRequest:
        request, role = self._pending_for_review(
            request_id, admin, PermissionName.ROLE_UPGRADE_REQUEST_APPROVE
        )
        assignment = self._assignments.get_for_update(request.user_id, role.id)
        if assignment is None or assignment.assigned_at > request.created_at:
            raise BusinessRuleError(RoleUpgradeRequestMessages.STALE_REQUEST)

        user = self._users.get(request.user_id)
        reviewed_at = app_now()
        assignment.verified_at = reviewed_at
        user.roles = [held for held in user.roles if held.slug != RoleSlug.INDIVIDUAL_USER]
        request.status = RoleUpgradeRequestStatus.APPROVED
        request.reviewed_by = admin.id
        request.reviewed_at = reviewed_at
        request.review_note = review_note
        saved_request = self._requests.save(request)

        role_name = role.name
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.ROLE_UPGRADE_APPROVED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"user_id": str(user.id), "role_id": str(request.requested_role_id)},
        )

        if user.email is not None:
            content = render_role_upgrade_approved_email(
                app_name=self._settings.app_name,
                role_name=role_name,
                support_url=self._settings.support_url,
                privacy_policy_url=self._settings.privacy_policy_url,
                terms_of_service_url=self._settings.terms_of_service_url,
            )
            self._emails.send(
                background_tasks,
                email_type=EmailType.ROLE_UPGRADE_APPROVED,
                to_email=user.email,
                subject=content.subject,
                text_body=content.text_body,
                html_body=content.html_body,
                user_id=user.id,
            )
        self._notifications.notify_role_upgrade_approved(
            recipient_id=user.id, actor=admin, request_id=request.id, role_name=role_name
        )
        self._publish_if_connected(
            user.id,
            RealtimeEventType.ROLE_UPGRADE_REQUEST_APPROVED,
            lambda: {
                "request_id": str(request.id),
                "status": RoleUpgradeRequestStatus.APPROVED.value,
                "role": RoleSummary.model_validate(role).model_dump(mode="json"),
            },
        )
        return saved_request

    def reject(
        self,
        request_id: UUID,
        admin: User,
        review_note: str,
        background_tasks: BackgroundTasks,
    ) -> RoleUpgradeRequest:
        request, role = self._pending_for_review(
            request_id, admin, PermissionName.ROLE_UPGRADE_REQUEST_REJECT
        )
        user = self._users.get(request.user_id)
        role_name = role.name

        request.status = RoleUpgradeRequestStatus.REJECTED
        request.reviewed_by = admin.id
        request.reviewed_at = app_now()
        request.review_note = review_note
        user.roles = [held for held in user.roles if held.id != role.id]
        saved_request = self._requests.save(request)

        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.ROLE_UPGRADE_REJECTED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"user_id": str(user.id), "role_id": str(request.requested_role_id)},
        )
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.ROLE_REMOVED,
            entity_type="user",
            entity_id=user.id,
            metadata={"role_id": str(role.id), "role_name": role_name},
        )

        if user.email is not None:
            content = render_role_upgrade_rejected_email(
                app_name=self._settings.app_name,
                role_name=role_name,
                review_note=review_note,
                support_url=self._settings.support_url,
                privacy_policy_url=self._settings.privacy_policy_url,
                terms_of_service_url=self._settings.terms_of_service_url,
            )
            self._emails.send(
                background_tasks,
                email_type=EmailType.ROLE_UPGRADE_REJECTED,
                to_email=user.email,
                subject=content.subject,
                text_body=content.text_body,
                html_body=content.html_body,
                user_id=user.id,
            )
        if role.slug == RoleSlug.CLUB_COMMUNITY:
            self._communities.reject_pending_of_owner(user.id, admin, review_note)
        self._notifications.notify_role_upgrade_rejected(
            recipient_id=user.id, actor=admin, request_id=request.id, role_name=role_name
        )
        self._publish_if_connected(
            user.id,
            RealtimeEventType.ROLE_UPGRADE_REQUEST_REJECTED,
            lambda: {
                "request_id": str(request.id),
                "status": RoleUpgradeRequestStatus.REJECTED.value,
            },
        )
        return saved_request

    def _pending_for_review(
        self, request_id: UUID, reviewer: User, permission: str
    ) -> tuple[RoleUpgradeRequest, Role]:
        request = self._requests.get_for_update(request_id)
        if request is None or not self._can_review(reviewer, request, permission):
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        if request.status != RoleUpgradeRequestStatus.PENDING:
            raise BusinessRuleError(RoleUpgradeRequestMessages.REQUEST_NOT_PENDING)
        if request.user_id == reviewer.id:
            raise AuthorizationError(RoleUpgradeRequestMessages.CANNOT_REVIEW_OWN_REQUEST)
        if request.requested_role is None:
            raise BusinessRuleError(RoleUpgradeRequestMessages.STALE_REQUEST)
        return request, request.requested_role

    @staticmethod
    def _can_review(reviewer: User, request: RoleUpgradeRequest, permission: str) -> bool:
        if has_permission(reviewer, permission):
            return True
        role = request.requested_role
        return (
            role is not None
            and role.slug in PROMOTER_REVIEW_ROLE_SLUGS
            and has_permission(reviewer, PermissionName.ROLE_UPGRADE_REQUEST_REVIEW_PROMOTER)
        )

    def _publish_request_created(
        self, request: RoleUpgradeRequest, role: Role, requester: User, reviewers: list[User]
    ) -> None:
        for reviewer in reviewers:
            if reviewer.id == requester.id:
                continue
            self._publish_if_connected(
                reviewer.id,
                RealtimeEventType.ROLE_UPGRADE_REQUEST_CREATED,
                lambda: {
                    "request_id": str(request.id),
                    "user": UserSummaryRead.model_validate(requester).model_dump(mode="json"),
                    "role": RoleSummary.model_validate(role).model_dump(mode="json"),
                },
            )

    def _publish_if_connected(
        self,
        recipient_id: UUID,
        event_type: RealtimeEventType,
        build_data: Callable[[], dict[str, Any]],
    ) -> None:
        try:
            if self._publisher.has_connections(recipient_id):
                self._publisher.publish_to_user(
                    recipient_id, RealtimeEvent(type=event_type, data=build_data())
                )
        except Exception:
            logger.exception("Failed to publish %s to user %s", event_type, recipient_id)
