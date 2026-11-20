from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.email_templates import render_plugin_approval_requested_email
from app.models.email import EmailType
from app.models.notification import NotificationType
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


def notify_approval_requested(
    db: Session,
    background_tasks: BackgroundTasks,
    requester: User,
    approver_id: UUID,
    entity_type: str,
    entity_id: UUID,
    item_name: str,
) -> None:
    NotificationService(db).notify_plugin_approval(
        approver_id,
        requester,
        NotificationType.PLUGIN_APPROVAL_REQUESTED,
        entity_type,
        entity_id,
        item_name,
    )
    approver = UserRepository(db).get_by_id(approver_id)
    if approver is None or approver.email is None:
        return
    settings = get_settings()
    content = render_plugin_approval_requested_email(
        app_name=settings.app_name,
        requester_name=f"{requester.first_name} {requester.last_name}",
        item_name=item_name,
        support_url=settings.support_url,
        privacy_policy_url=settings.privacy_policy_url,
        terms_of_service_url=settings.terms_of_service_url,
    )
    EmailService(db, settings).send(
        background_tasks,
        email_type=EmailType.PLUGIN_APPROVAL_REQUESTED,
        to_email=approver.email,
        subject=content.subject,
        text_body=content.text_body,
        html_body=content.html_body,
        user_id=approver.id,
    )


def notify_approval_decided(
    db: Session,
    approver: User,
    requester_id: UUID,
    entity_type: str,
    entity_id: UUID,
    item_name: str,
    approved: bool,
    review_note: str | None = None,
) -> None:
    NotificationService(db).notify_plugin_approval(
        requester_id,
        approver,
        (
            NotificationType.PLUGIN_APPROVAL_APPROVED
            if approved
            else NotificationType.PLUGIN_APPROVAL_REJECTED
        ),
        entity_type,
        entity_id,
        item_name,
        review_note,
    )
