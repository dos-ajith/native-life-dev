import logging
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.database import SessionLocal
from app.core.email import EmailProvider, OutgoingEmail, get_email_provider
from app.models.email import Email, EmailStatus, EmailType
from app.repositories.email_repository import EmailRepository
from app.repositories.setting_repository import SettingRepository

logger = logging.getLogger(__name__)

MANDRILL_ENABLED_SETTING_KEY = "mandrill_enabled"
_TRUE_VALUES = {"true", "1", "yes", "on"}
_FALSE_VALUES = {"false", "0", "no", "off"}


def _dispatch_self_hosted_email(
    provider: EmailProvider,
    settings: Settings,
    email_id: UUID,
    to_email: str,
    subject: str,
    text_body: str,
    html_body: str,
) -> None:
    db = SessionLocal()
    try:
        repo = EmailRepository(db)
        email = repo.get_by_id(email_id)
        if email is None:
            return
        result = provider.send(
            OutgoingEmail(
                to_email=to_email,
                from_email=settings.mail_from_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
            )
        )
        if result.success:
            repo.mark_sent(email, result.provider_message_id)
        else:
            repo.mark_failed(email, result.error_code, result.error_message)
    except Exception:
        logger.exception("Failed to send self-hosted email %s to %s", email_id, to_email)
    finally:
        db.close()


def _parse_bool_setting(raw_value: str | None, default: bool) -> bool:
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


class EmailService:
    def __init__(
        self, db: Session, settings: Settings, provider: EmailProvider | None = None
    ) -> None:
        self._emails = EmailRepository(db)
        self._app_settings = SettingRepository(db)
        self._settings = settings
        self._provider = provider or get_email_provider()

    def _is_mandrill_enabled(self) -> bool:
        setting = self._app_settings.get_by_key(MANDRILL_ENABLED_SETTING_KEY)
        return _parse_bool_setting(
            setting.value if setting is not None else None, self._settings.mandrill_enabled
        )

    def send(
        self,
        background_tasks: BackgroundTasks,
        email_type: EmailType,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        user_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Email:
        mandrill_enabled = self._is_mandrill_enabled()

        email = self._emails.create(
            Email(
                user_id=user_id,
                to_email=to_email,
                from_email=self._settings.mail_from_email,
                subject=subject,
                text_body=text_body,
                html_body=html_body,
                email_type=email_type,
                provider="mandrill" if mandrill_enabled else self._provider.name,
                status=EmailStatus.PENDING,
                metadata_=metadata,
            )
        )

        if mandrill_enabled:
            return email

        background_tasks.add_task(
            _dispatch_self_hosted_email,
            self._provider,
            self._settings,
            email.id,
            to_email,
            subject,
            text_body,
            html_body,
        )
        return email
