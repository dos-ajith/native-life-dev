import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()
_OTP_DIGITS = "0123456789"
_REFRESH_TOKEN_BYTES = 32


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        return False
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_otp(length: int) -> str:
    return "".join(secrets.choice(_OTP_DIGITS) for _ in range(length))


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(_REFRESH_TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
