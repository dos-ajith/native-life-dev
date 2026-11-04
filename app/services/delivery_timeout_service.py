from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import DeliveryMessages
from app.repositories.setting_repository import SettingRepository

DELIVERY_RESPONSE_MINUTES_SETTING_KEY = "delivery_response_minutes"
DELIVERY_CLAIM_MINUTES_SETTING_KEY = "delivery_claim_minutes"
DELIVERY_TIMEOUT_SETTING_KEYS = frozenset(
    {DELIVERY_RESPONSE_MINUTES_SETTING_KEY, DELIVERY_CLAIM_MINUTES_SETTING_KEY}
)
DEFAULT_DELIVERY_RESPONSE_MINUTES = 30
DEFAULT_DELIVERY_CLAIM_MINUTES = 60
MIN_DELIVERY_TIMEOUT_MINUTES = 1
MAX_DELIVERY_TIMEOUT_MINUTES = 1440


def parse_timeout_minutes(key: str, raw: str | None) -> int:
    message = DeliveryMessages.TIMEOUT_INVALID.format(
        key=key, minimum=MIN_DELIVERY_TIMEOUT_MINUTES, maximum=MAX_DELIVERY_TIMEOUT_MINUTES
    )
    if raw is None or not raw.strip().isdigit():
        raise BusinessRuleError(message)
    minutes = int(raw.strip())
    if not MIN_DELIVERY_TIMEOUT_MINUTES <= minutes <= MAX_DELIVERY_TIMEOUT_MINUTES:
        raise BusinessRuleError(message)
    return minutes


class DeliveryTimeoutService:
    def __init__(self, db: Session) -> None:
        self._settings = SettingRepository(db)

    def response_window(self) -> timedelta:
        return self._window(
            DELIVERY_RESPONSE_MINUTES_SETTING_KEY, DEFAULT_DELIVERY_RESPONSE_MINUTES
        )

    def claim_window(self) -> timedelta:
        return self._window(DELIVERY_CLAIM_MINUTES_SETTING_KEY, DEFAULT_DELIVERY_CLAIM_MINUTES)

    def ensure_valid(self, key: str, value: str | None) -> None:
        parse_timeout_minutes(key, value)

    def _window(self, key: str, default_minutes: int) -> timedelta:
        setting = self._settings.get_by_key(key)
        if setting is None:
            return timedelta(minutes=default_minutes)
        return timedelta(minutes=parse_timeout_minutes(key, setting.value))
