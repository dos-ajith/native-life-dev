from datetime import UTC, datetime
from uuid import UUID

from fastapi import BackgroundTasks, UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.email_templates import (
    render_role_upgrade_approved_email,
    render_role_upgrade_rejected_email,
)
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import RoleUpgradeRequestMessages
from app.core.permissions import NON_REQUESTABLE_ROLE_SLUGS, PermissionName
from app.core.storage import save_role_upgrade_document
from app.models.email import EmailType
from app.models.role import Role
from app.models.role_upgrade_request import RoleUpgradeRequest, RoleUpgradeRequestStatus
from app.models.role_upgrade_request_document import RoleUpgradeRequestDocument
from app.models.user import User
from app.repositories.role_repository import RoleRepository
from app.repositories.role_upgrade_request_document_repository import (
    RoleUpgradeRequestDocumentRepository,
)
from app.repositories.role_upgrade_request_repository import RoleUpgradeRequestRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService
from app.services.user_service import UserService


class RoleUpgradeRequestService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._requests = RoleUpgradeRequestRepository(db)
        self._documents = RoleUpgradeRequestDocumentRepository(db)
        self._roles = RoleRepository(db)
        self._users = UserService(db)
        self._activity_logs = ActivityLogService(db)
        self._notifications = NotificationService(db)
        self._emails = EmailService(db, settings)

    def list_requestable_roles(self, actor: User) -> list[Role]:
        return self._roles.list_excluding(
            NON_REQUESTABLE_ROLE_SLUGS, {role.id for role in actor.roles}
        )

    def submit(
        self,
        actor: User,
        requested_role_id: UUID,
        reason: str | None,
        document: UploadFile | None,
    ) -> RoleUpgradeRequest:
        role = self._roles.get_by_id(requested_role_id)
        if role is None:
            raise BusinessRuleError(RoleUpgradeRequestMessages.UNKNOWN_ROLE)
        if role.slug in NON_REQUESTABLE_ROLE_SLUGS:
            raise BusinessRuleError(RoleUpgradeRequestMessages.RESTRICTED_ROLE)
        if any(existing_role.id == role.id for existing_role in actor.roles):
            raise BusinessRuleError(RoleUpgradeRequestMessages.ALREADY_HAS_ROLE)

        saved_document: tuple[str, str, int] | None = None
        document_filename: str | None = None
        if document is not None:
            saved_document = save_role_upgrade_document(document, self._settings.private_upload_dir)
            document_filename = document.filename

        request = self._requests.create_pending(actor.id, requested_role_id, reason)
        if request is None:
            raise BusinessRuleError(RoleUpgradeRequestMessages.DUPLICATE_PENDING_REQUEST)

        if saved_document is not None:
            storage_path, content_type, size_bytes = saved_document
            self._documents.add(
                RoleUpgradeRequestDocument(
                    request_id=request.id,
                    file_name=document_filename or "document",
                    content_type=content_type,
                    file_size_bytes=size_bytes,
                    storage_path=storage_path,
                )
            )

        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ROLE_UPGRADE_REQUESTED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"requested_role_id": str(role.id), "role_name": role.name},
        )
        return request

    def add_document(
        self, actor: User, request_id: UUID, document: UploadFile
    ) -> RoleUpgradeRequestDocument:
        request = self._requests.get_by_id_for_user(request_id, actor.id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        if request.status != RoleUpgradeRequestStatus.PENDING:
            raise BusinessRuleError(RoleUpgradeRequestMessages.REQUEST_NOT_PENDING)

        doc = self._attach_document(request, document)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.ROLE_UPGRADE_DOCUMENT_ADDED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"document_id": str(doc.id)},
        )
        return doc

    def _attach_document(
        self, request: RoleUpgradeRequest, document: UploadFile
    ) -> RoleUpgradeRequestDocument:
        storage_path, content_type, size_bytes = save_role_upgrade_document(
            document, self._settings.private_upload_dir
        )
        return self._documents.add(
            RoleUpgradeRequestDocument(
                request_id=request.id,
                file_name=document.filename or "document",
                content_type=content_type,
                file_size_bytes=size_bytes,
                storage_path=storage_path,
            )
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

    def get_for_admin(self, request_id: UUID) -> RoleUpgradeRequest:
        request = self._requests.get_by_id(request_id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.NOT_FOUND)
        return request

    def list_pending(self, params: PaginationParams) -> tuple[list[RoleUpgradeRequest], int]:
        return self._requests.list_pending(params)

    def get_document_for_download(
        self, actor: User, request_id: UUID, document_id: UUID
    ) -> RoleUpgradeRequestDocument:
        document = self._documents.get_by_id(document_id)
        if document is None or document.request_id != request_id:
            raise NotFoundError(RoleUpgradeRequestMessages.DOCUMENT_NOT_FOUND)
        request = self._requests.get_by_id(document.request_id)
        if request is None:
            raise NotFoundError(RoleUpgradeRequestMessages.DOCUMENT_NOT_FOUND)
        if request.user_id != actor.id and not has_permission(
            actor, PermissionName.ROLE_UPGRADE_REQUEST_VIEW_ANY
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
        request = self.get_for_admin(request_id)
        if request.status != RoleUpgradeRequestStatus.PENDING:
            raise BusinessRuleError(RoleUpgradeRequestMessages.REQUEST_NOT_PENDING)

        user = self._users.get(request.user_id)
        role_ids = {role.id for role in user.roles}
        role_ids.add(request.requested_role_id)
        self._users.assign_roles(user.id, list(role_ids), actor=admin)

        request.status = RoleUpgradeRequestStatus.APPROVED
        request.reviewed_by = admin.id
        request.reviewed_at = datetime.now(UTC)
        request.review_note = review_note
        saved_request = self._requests.save(request)

        role_name = request.requested_role.name
        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.ROLE_UPGRADE_APPROVED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"user_id": str(user.id), "role_id": str(request.requested_role_id)},
        )

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
        return saved_request

    def reject(
        self,
        request_id: UUID,
        admin: User,
        review_note: str,
        background_tasks: BackgroundTasks,
    ) -> RoleUpgradeRequest:
        request = self.get_for_admin(request_id)
        if request.status != RoleUpgradeRequestStatus.PENDING:
            raise BusinessRuleError(RoleUpgradeRequestMessages.REQUEST_NOT_PENDING)

        user = self._users.get(request.user_id)
        role_name = request.requested_role.name

        request.status = RoleUpgradeRequestStatus.REJECTED
        request.reviewed_by = admin.id
        request.reviewed_at = datetime.now(UTC)
        request.review_note = review_note
        saved_request = self._requests.save(request)

        self._activity_logs.log(
            actor=admin,
            action=ActivityAction.ROLE_UPGRADE_REJECTED,
            entity_type="role_upgrade_request",
            entity_id=request.id,
            metadata={"user_id": str(user.id), "role_id": str(request.requested_role_id)},
        )

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
        self._notifications.notify_role_upgrade_rejected(
            recipient_id=user.id, actor=admin, request_id=request.id, role_name=role_name
        )
        return saved_request
