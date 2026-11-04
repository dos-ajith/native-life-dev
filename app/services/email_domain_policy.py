from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import UserMessages


def ensure_email_domain_allowed(email: str, settings: Settings) -> None:
    allowed = {domain.lower() for domain in settings.registration_allowed_email_domains}
    if allowed and email.rsplit("@", 1)[-1].lower() not in allowed:
        raise BusinessRuleError(UserMessages.EMAIL_DOMAIN_NOT_ALLOWED)
