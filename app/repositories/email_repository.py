from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.email import Email, EmailStatus


class EmailRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, email: Email) -> Email:
        self._db.add(email)
        self._db.commit()
        self._db.refresh(email)
        return email

    def get_by_id(self, email_id: UUID) -> Email | None:
        return self._db.get(Email, email_id)

    def mark_sent(self, email: Email, provider_message_id: str | None) -> None:
        email.status = EmailStatus.SENT
        email.provider_message_id = provider_message_id
        email.sent_at = datetime.now(UTC)
        self._db.commit()

    def mark_failed(self, email: Email, error_code: str | None, error_message: str | None) -> None:
        email.status = EmailStatus.FAILED
        email.error_code = error_code
        email.error_message = error_message
        email.failed_at = datetime.now(UTC)
        self._db.commit()
