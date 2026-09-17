from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt as pyjwt
import pytest

from app.core.config import get_settings
from app.core.jwt import create_access_token, decode_access_token

settings = get_settings()


def test_create_and_decode_access_token_roundtrip() -> None:
    user_id = uuid4()

    issued = create_access_token(user_id, settings)
    payload = decode_access_token(issued.token, settings)

    assert payload["sub"] == str(user_id)
    assert payload["jti"] == str(issued.jti)


def test_decode_access_token_rejects_expired_token() -> None:
    now = datetime.now(UTC)
    expired_payload = {
        "sub": str(uuid4()),
        "iat": now - timedelta(minutes=10),
        "exp": now - timedelta(minutes=1),
    }
    token = pyjwt.encode(
        expired_payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )

    with pytest.raises(pyjwt.ExpiredSignatureError):
        decode_access_token(token, settings)


def test_decode_access_token_rejects_bad_signature() -> None:
    token = pyjwt.encode(
        {"sub": str(uuid4())}, "a-different-secret", algorithm=settings.jwt_algorithm
    )

    with pytest.raises(pyjwt.InvalidSignatureError):
        decode_access_token(token, settings)
