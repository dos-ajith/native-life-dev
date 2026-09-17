from collections.abc import Iterator
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.models.active_token import ActiveToken
from app.models.user import User, UserStatus

SELF_EMAIL = "users-integration-self@example.com"
SELF_PASSWORD = "correct-horse-battery-staple"
REGISTER_EMAIL = "users-integration-register@example.com"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
    db.commit()
    db.close()


def _delete_user(user_id: UUID) -> None:
    db = SessionLocal()
    db.execute(delete(User).where(User.id == user_id))
    db.commit()
    db.close()


@pytest.fixture
def self_user() -> Iterator[User]:
    db = SessionLocal()
    user = User(
        first_name="Self",
        last_name="User",
        email=SELF_EMAIL,
        password_hash=hash_password(SELF_PASSWORD),
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield user
    finally:
        db.delete(user)
        db.commit()
        db.close()


@pytest.fixture
def auth_headers(client: TestClient, self_user: User) -> Iterator[dict[str, str]]:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": SELF_EMAIL, "password": SELF_PASSWORD}
    )
    token = login_response.json()["data"]["access_token"]
    try:
        yield {"Authorization": f"Bearer {token}"}
    finally:
        _delete_active_token(token)


def test_register_creates_active_public_user(client: TestClient) -> None:
    response = client.post(
        "/api/v1/users/register",
        json={
            "first_name": "New",
            "last_name": "Customer",
            "email": REGISTER_EMAIL,
            "password": "SomePassword123!",
        },
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["email"] == REGISTER_EMAIL
    assert body["status"] == "active"
    assert body["user_type"] == "public"

    _delete_user(UUID(body["id"]))


def test_register_rejects_duplicate_email(client: TestClient, self_user: User) -> None:
    response = client.post(
        "/api/v1/users/register",
        json={
            "first_name": "Dup",
            "last_name": "Customer",
            "email": SELF_EMAIL,
            "password": "SomePassword123!",
        },
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


def test_update_me_updates_own_profile(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.patch(
        "/api/v1/users/me",
        json={"first_name": "SelfUpdated", "profile_image_url": "https://example.com/a.png"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["first_name"] == "SelfUpdated"
    assert body["profile_image_url"] == "https://example.com/a.png"


def test_update_me_rejects_missing_token(client: TestClient) -> None:
    response = client.patch("/api/v1/users/me", json={"first_name": "SelfUpdated"})

    assert response.status_code == 401
