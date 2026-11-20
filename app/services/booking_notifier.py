from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.email_templates import render_booking_requested_email
from app.models.booking import Booking
from app.models.email import EmailType
from app.models.notification import NotificationType
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.email_service import EmailService
from app.services.notification_service import NotificationService


class BookingNotifier:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._notifications = NotificationService(db)
        self._users = UserRepository(db)

    def requested(
        self, booking: Booking, owner_id: UUID, actor: User, tasks: BackgroundTasks
    ) -> None:
        self._notify(owner_id, actor, NotificationType.BOOKING_REQUESTED, booking, None)
        owner = self._users.get_by_id(owner_id)
        if owner is None or owner.email is None:
            return
        settings = get_settings()
        content = render_booking_requested_email(
            app_name=settings.app_name,
            customer_name=booking.customer_name,
            booking_number=booking.booking_number,
            item_name=booking.item_name,
            support_url=settings.support_url,
            privacy_policy_url=settings.privacy_policy_url,
            terms_of_service_url=settings.terms_of_service_url,
        )
        EmailService(self._db, settings).send(
            tasks,
            email_type=EmailType.BOOKING_REQUESTED,
            to_email=owner.email,
            subject=content.subject,
            text_body=content.text_body,
            html_body=content.html_body,
            user_id=owner.id,
        )

    def responded(
        self,
        booking: Booking,
        recipient_id: UUID,
        actor: User,
        type_: NotificationType,
        note: str | None,
    ) -> None:
        self._notify(recipient_id, actor, type_, booking, note)

    def paid(self, booking: Booking, owner_id: UUID, customer: User) -> None:
        self._notify(owner_id, customer, NotificationType.BOOKING_PAID, booking, None)

    def _notify(
        self,
        recipient_id: UUID,
        actor: User,
        type_: NotificationType,
        booking: Booking,
        note: str | None,
    ) -> None:
        self._notifications.notify_booking(
            recipient_id, actor, type_, booking.id, booking.booking_number, booking.item_name, note
        )
