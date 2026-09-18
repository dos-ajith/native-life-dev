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
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.utils.slug import slugify

ADMIN_EMAIL = "roles-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
CUSTOMER_EMAIL = "roles-integration-customer@example.com"
ROLE_NAME = "roles-integration.editor"
CONFLICT_ROLE_NAME = "roles-integration.conflict"
PERMISSION_NAME = "roles-integration.permission"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
    db.commit()
    db.close()


def _delete_role(role_id: UUID) -> None:
    db = SessionLocal()
    db.execute(delete(Role).where(Role.id == role_id))
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
def role() -> Iterator[Role]:
    db = SessionLocal()
    role = Role(
        name=ROLE_NAME, slug=slugify(ROLE_NAME), description="Can edit things", permissions=[]
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    try:
        yield role
    finally:
        db.execute(delete(Role).where(Role.id == role.id))
        db.commit()
        db.close()


@pytest.fixture
def permission() -> Iterator[Permission]:
    db = SessionLocal()
    permission = Permission(name=PERMISSION_NAME, description="A permission")
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


def test_create_role_returns_created_role(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/roles/create",
        json={"name": ROLE_NAME, "description": "Can edit things"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["name"] == ROLE_NAME
    assert body["permissions"] == []

    _delete_role(UUID(body["id"]))


def test_create_role_rejects_duplicate_name(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.post(
        "/api/v1/admin/roles/create",
        json={"name": ROLE_NAME},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_role_rejects_missing_token(client: TestClient) -> None:
    response = client.post("/api/v1/admin/roles/create", json={"name": ROLE_NAME})

    assert response.status_code == 401


def test_create_role_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/roles/create",
        json={"name": ROLE_NAME},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_list_roles_returns_paginated_page(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.get("/api/v1/admin/roles?page=1&page_size=5", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["total"] >= 1


def test_get_role_returns_role(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.get(f"/api/v1/admin/roles/edit/{role.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["name"] == ROLE_NAME


def test_get_role_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(f"/api/v1/admin/roles/edit/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_update_role_changes_fields(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.patch(
        f"/api/v1/admin/roles/update/{role.id}",
        json={"description": "Updated description"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["description"] == "Updated description"


def test_delete_role_removes_role(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.delete(f"/api/v1/admin/roles/delete/{role.id}", headers=admin_headers)

    assert response.status_code == 200

    get_response = client.get(f"/api/v1/admin/roles/edit/{role.id}", headers=admin_headers)
    assert get_response.status_code == 404


def test_set_role_permissions_assigns_permissions(
    client: TestClient, admin_headers: dict[str, str], role: Role, permission: Permission
) -> None:
    response = client.put(
        f"/api/v1/admin/roles/update/{role.id}/permissions",
        json={"permission_ids": [str(permission.id)]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert [p["id"] for p in body["permissions"]] == [str(permission.id)]


def test_set_role_permissions_rejects_unknown_permission_id(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.put(
        f"/api/v1/admin/roles/update/{role.id}/permissions",
        json={"permission_ids": [str(uuid4())]},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_set_role_permissions_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], role: Role, permission: Permission
) -> None:
    response = client.put(
        f"/api/v1/admin/roles/update/{role.id}/permissions",
        json={"permission_ids": [str(permission.id)]},
        headers=customer_headers,
    )

    assert response.status_code == 403
