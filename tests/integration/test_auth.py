from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.models.active_token import ActiveToken
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User, UserStatus

TEST_EMAIL = "auth-integration-test@example.com"
TEST_PASSWORD = "correct-horse-battery-staple"
ROLE_NAME = "auth-integration.role"
PERMISSION_NAME = "auth-integration.permission"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
    db.commit()
    db.close()


@pytest.fixture
def active_user() -> Iterator[User]:
    db = SessionLocal()
    user = User(
        first_name="Test",
        last_name="User",
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
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


def test_login_returns_access_token(client: TestClient, active_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"]
    assert body["data"]["user"]["email"] == TEST_EMAIL
    assert body["data"]["user"]["roles"] == []

    _delete_active_token(body["data"]["access_token"])


def test_login_rejects_wrong_password(client: TestClient, active_user: User) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": "wrong-password"}
    )

    assert response.status_code == 401
    assert response.json()["success"] is False


def test_login_rejects_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever"}
    )

    assert response.status_code == 401


@pytest.fixture
def active_user_with_role() -> Iterator[User]:
    db = SessionLocal()
    permission = Permission(name=PERMISSION_NAME, description="A permission")
    role = Role(name=ROLE_NAME, description="A role", permissions=[permission])
    user = User(
        first_name="Test",
        last_name="User",
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        status=UserStatus.ACTIVE,
        roles=[role],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield user
    finally:
        db.delete(user)
        db.execute(delete(Role).where(Role.id == role.id))
        db.execute(delete(Permission).where(Permission.id == permission.id))
        db.commit()
        db.close()


def test_me_returns_current_user_with_roles_and_permissions(
    client: TestClient, active_user_with_role: User
) -> None:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["data"]["access_token"]

    try:
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        body = response.json()["data"]
        assert body["email"] == TEST_EMAIL
        assert [r["name"] for r in body["roles"]] == [ROLE_NAME]
        assert [p["name"] for p in body["roles"][0]["permissions"]] == [PERMISSION_NAME]
    finally:
        _delete_active_token(token)


def test_me_returns_current_user(client: TestClient, active_user: User) -> None:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["data"]["access_token"]

    try:
        response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"]["email"] == TEST_EMAIL
    finally:
        _delete_active_token(token)


def test_me_rejects_missing_token(client: TestClient) -> None:
    response = client.get("/api/v1/auth/me")

    assert response.status_code == 401


def test_logout_deactivates_token(client: TestClient, active_user: User) -> None:
    login_response = client.post(
        "/api/v1/auth/login", json={"email": TEST_EMAIL, "password": TEST_PASSWORD}
    )
    token = login_response.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    logout_response = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_response.status_code == 200
    assert logout_response.json()["success"] is True

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.status_code == 401


def test_logout_rejects_missing_token(client: TestClient) -> None:
    response = client.post("/api/v1/auth/logout")

    assert response.status_code == 401
