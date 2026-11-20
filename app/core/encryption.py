from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailableError
from app.core.messages import PayoutAccountMessages


class FieldCipher:
    def __init__(self, fernet: Fernet) -> None:
        self._fernet = fernet

    @classmethod
    def from_settings(cls, settings: Settings) -> "FieldCipher":
        key = settings.payout_account_encryption_key
        if key is None:
            raise ServiceUnavailableError(PayoutAccountMessages.ENCRYPTION_DISABLED)
        try:
            return cls(Fernet(key.get_secret_value().encode()))
        except (ValueError, TypeError) as exc:
            raise ServiceUnavailableError(PayoutAccountMessages.ENCRYPTION_DISABLED) from exc

    def encrypt(self, plain: str) -> str:
        return self._fernet.encrypt(plain.encode()).decode()

    def decrypt(self, token: str) -> str:
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken as exc:
            raise ServiceUnavailableError(PayoutAccountMessages.ENCRYPTION_DISABLED) from exc
