import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings

logger = logging.getLogger(__name__)


def send_email(to_email: str, subject: str, body: str, settings: Settings) -> None:
    if not settings.smtp_host or not settings.mail_from_email:
        logger.error("Email not sent to %s: SMTP is not configured", to_email)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.app_name} <{settings.mail_from_email}>"
    message["To"] = to_email
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(message)
    except (smtplib.SMTPException, OSError):
        logger.exception("Failed to send email to %s", to_email)


def send_email_verification_otp(
    to_email: str, otp: str, expire_minutes: int, settings: Settings
) -> None:
    subject = f"Your {settings.app_name} verification code"
    body = f"Your verification code is: {otp}\n\nThis code will expire in {expire_minutes} minutes."
    send_email(to_email, subject, body, settings)
