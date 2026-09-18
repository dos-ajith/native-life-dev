from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.models.active_token import ActiveToken
from app.models.permission import Permission
from app.models.user import User, UserStatus, UserType

ADMIN_EMAIL = "permissions-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
CUSTOMER_EMAIL = "permissions-integration-customer@example.com"
PERMISSION_NAME = "permissions-integration.view"
CONFLICT_PERMISSION_NAME = "permissions-integration.conflict"


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


def _delete_permission(permission_id: UUID) -> None:
    db = SessionLocal()
    db.execute(delete(Permission).where(Permission.id == permission_id))
    db.commit()
    db.close()


def _create_user(email: str, password: str, user_type: UserType) -> Iterator[User]:
    db = SessionLocal()
    user = User(
        first_name="Test",
        last_name="User",
        email=email,
        password_hash=hash_password(password),
        status=UserStatus.ACTIVE,
        user_type=user_type,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        yield user
    finally:
        db.execute(delete(User).where(User.id == user.id))
        db.commit()
        db.close()


@pytest.fixture
def admin_actor() -> Iterator[User]:
    yield from _create_user(ADMIN_EMAIL, ADMIN_PASSWORD, UserType.PRIVATE)


@pytest.fixture
def customer_actor() -> Iterator[User]:
    yield from _create_user(CUSTOMER_EMAIL, "whatever-password", UserType.PUBLIC)


@pytest.fixture
def permission() -> Iterator[Permission]:
    db = SessionLocal()
    permission = Permission(name=PERMISSION_NAME, description="View things")
    db.add(permission)
    db.commit()
    db.refresh(permission)
    try:
        yield permission
    finally:
        db.execute(delete(Permission).where(Permission.id == permission.id))
        db.commit()
        db.close()


def _login_headers(client: TestClient, email: str, password: str) -> Iterator[dict[str, str]]:
    login_response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = login_response.json()["data"]["access_token"]
    try:
        yield {"Authorization": f"Bearer {token}"}
    finally:
        _delete_active_token(token)


@pytest.fixture
def admin_headers(client: TestClient, admin_actor: User) -> Iterator[dict[str, str]]:
    yield from _login_headers(client, ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture
def customer_headers(client: TestClient, customer_actor: User) -> Iterator[dict[str, str]]:
    yield from _login_headers(client, CUSTOMER_EMAIL, "whatever-password")


def test_create_permission_returns_created_permission(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": PERMISSION_NAME, "description": "View things"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == PERMISSION_NAME

    _delete_permission(UUID(body["id"]))


def test_create_permission_rejects_duplicate_name(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": PERMISSION_NAME},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_permission_rejects_blank_name(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": "   "},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_permission_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": PERMISSION_NAME},
    )

    assert response.status_code == 401


def test_create_permission_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": PERMISSION_NAME},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_list_permissions_returns_paginated_page(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    response = client.get("/api/v1/admin/permissions?page=1&page_size=5", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 1


def test_get_permission_returns_permission(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    response = client.get(
        f"/api/v1/admin/permissions/edit/{permission.id}", headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["data"]["name"] == PERMISSION_NAME


def test_get_permission_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(f"/api/v1/admin/permissions/edit/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_update_permission_changes_fields(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    response = client.patch(
        f"/api/v1/admin/permissions/update/{permission.id}",
        data={"description": "Updated description"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Updated description"


def test_update_permission_rejects_duplicate_name(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    create_response = client.post(
        "/api/v1/admin/permissions/create",
        data={"name": CONFLICT_PERMISSION_NAME},
        headers=admin_headers,
    )
    conflict_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/admin/permissions/update/{conflict_id}",
        data={"name": PERMISSION_NAME},
        headers=admin_headers,
    )

    assert response.status_code == 422
    _delete_permission(UUID(conflict_id))


def test_delete_permission_removes_permission(
    client: TestClient, admin_headers: dict[str, str], permission: Permission
) -> None:
    response = client.delete(
        f"/api/v1/admin/permissions/delete/{permission.id}", headers=admin_headers
    )

    assert response.status_code == 200

    get_response = client.get(
        f"/api/v1/admin/permissions/edit/{permission.id}", headers=admin_headers
    )
    assert get_response.status_code == 404
