import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage as MimeMessage
from email.utils import make_msgid
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    to_email: str
    from_email: str | None
    subject: str
    text_body: str
    html_body: str | None = None


@dataclass(frozen=True)
class EmailSendResult:
    success: bool
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None


class EmailProvider(Protocol):
    name: str

    def send(self, message: OutgoingEmail) -> EmailSendResult: ...


class SmtpEmailProvider:
    name: str = "smtp"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: OutgoingEmail) -> EmailSendResult:
        if not self._settings.smtp_host or not message.from_email:
            logger.error("Email not sent to %s: SMTP is not configured", message.to_email)
            return EmailSendResult(
                success=False,
                error_code="smtp_not_configured",
                error_message="SMTP host or from-address is not configured",
            )

        message_id = make_msgid()
        mime_message = MimeMessage()
        mime_message["Message-Id"] = message_id
        mime_message["Subject"] = message.subject
        mime_message["From"] = f"{self._settings.app_name} <{message.from_email}>"
        mime_message["To"] = message.to_email
        mime_message.set_content(message.text_body)
        if message.html_body is not None:
            mime_message.add_alternative(message.html_body, subtype="html")

        try:
            with smtplib.SMTP(
                self._settings.smtp_host, self._settings.smtp_port, timeout=10
            ) as server:
                if self._settings.smtp_use_tls:
                    server.starttls()
                if self._settings.smtp_username and self._settings.smtp_password:
                    server.login(self._settings.smtp_username, self._settings.smtp_password)
                refused = server.send_message(mime_message)
        except (smtplib.SMTPException, OSError) as exc:
            logger.exception("Failed to send email to %s", message.to_email)
            return EmailSendResult(
                success=False, error_code=type(exc).__name__, error_message=str(exc)
            )

        if refused:
            logger.error("Recipients refused for %s: %s", message.to_email, refused)
            return EmailSendResult(
                success=False,
                error_code="recipient_refused",
                error_message=f"Refused for: {', '.join(refused)}",
            )

        return EmailSendResult(success=True, provider_message_id=message_id)


@lru_cache
def get_email_provider() -> EmailProvider:
    return SmtpEmailProvider(get_settings())
