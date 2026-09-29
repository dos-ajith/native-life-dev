import logging
import smtplib
from email.message import EmailMessage

from app.core.config import Settings
from app.core.email_templates import render_verification_otp_email

logger = logging.getLogger(__name__)


def send_email(
    to_email: str, subject: str, text_body: str, settings: Settings, html_body: str | None = None
) -> None:
    if not settings.smtp_host or not settings.mail_from_email:
        logger.error("Email not sent to %s: SMTP is not configured", to_email)
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.app_name} <{settings.mail_from_email}>"
    message["To"] = to_email
    message.set_content(text_body)
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")

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
    content = render_verification_otp_email(
        app_name=settings.app_name,
        otp=otp,
        expire_minutes=expire_minutes,
        support_url=settings.support_url,
        privacy_policy_url=settings.privacy_policy_url,
        terms_of_service_url=settings.terms_of_service_url,
    )
    send_email(to_email, content.subject, content.text_body, settings, html_body=content.html_body)
