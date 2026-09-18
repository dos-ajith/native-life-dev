from collections.abc import Iterator
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.models.active_token import ActiveToken
from app.models.role import Role
from app.models.user import User, UserStatus, UserType
from app.utils.slug import slugify

ADMIN_EMAIL = "admin-users-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
TARGET_EMAIL = "admin-users-integration-target@example.com"
CONFLICT_EMAIL = "admin-users-integration-conflict@example.com"
ROLE_NAME = "admin-users-integration.role"


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
def target_user() -> Iterator[User]:
    yield from _create_user(TARGET_EMAIL, "whatever-password", UserType.PUBLIC)


@pytest.fixture
def conflict_user() -> Iterator[User]:
    yield from _create_user(CONFLICT_EMAIL, "whatever-password", UserType.PUBLIC)


@pytest.fixture
def role() -> Iterator[Role]:
    db = SessionLocal()
    role = Role(name=ROLE_NAME, slug=slugify(ROLE_NAME), description="A role", permissions=[])
    db.add(role)
    db.commit()
    db.refresh(role)
    try:
        yield role
    finally:
        db.execute(delete(Role).where(Role.id == role.id))
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
def customer_headers(client: TestClient, target_user: User) -> Iterator[dict[str, str]]:
    yield from _login_headers(client, TARGET_EMAIL, "whatever-password")


def test_create_user_returns_created_user(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "New",
            "last_name": "Person",
            "email": "admin-users-integration-created@example.com",
            "password": "SomePassword123!",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["data"]["email"] == "admin-users-integration-created@example.com"
    assert body["data"]["status"] == "active"

    _delete_user(UUID(body["data"]["id"]))


def test_create_user_ignores_client_supplied_user_type(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "New",
            "last_name": "Person",
            "email": "admin-users-integration-type-override@example.com",
            "password": "SomePassword123!",
            "user_type": "public",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]

    db = SessionLocal()
    try:
        created = db.get(User, UUID(body["id"]))
        assert created is not None
        assert created.user_type == UserType.PRIVATE
    finally:
        db.close()

    _delete_user(UUID(body["id"]))


def test_create_user_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "New",
            "last_name": "Person",
            "email": "admin-users-integration-unauth@example.com",
            "password": "SomePassword123!",
        },
    )

    assert response.status_code == 401


def test_create_user_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "New",
            "last_name": "Person",
            "email": "admin-users-integration-forbidden@example.com",
            "password": "SomePassword123!",
        },
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_create_user_rejects_duplicate_email(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "Dup",
            "last_name": "User",
            "email": TARGET_EMAIL,
            "password": "SomePassword123!",
        },
        headers=admin_headers,
    )

    assert response.status_code == 422
    assert response.json()["success"] is False


def test_get_user_returns_user(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.get(f"/api/v1/admin/users/edit/{target_user.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["email"] == TARGET_EMAIL


def test_get_user_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(f"/api/v1/admin/users/edit/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_get_user_rejects_missing_token(client: TestClient, target_user: User) -> None:
    response = client.get(f"/api/v1/admin/users/edit/{target_user.id}")

    assert response.status_code == 401


def test_get_user_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], target_user: User
) -> None:
    response = client.get(f"/api/v1/admin/users/edit/{target_user.id}", headers=customer_headers)

    assert response.status_code == 403


def test_list_users_returns_paginated_page(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.get("/api/v1/admin/users?page=1&page_size=5", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 1
    assert isinstance(data["items"], list)


def test_list_users_rejects_page_size_above_limit(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/admin/users?page_size=500", headers=admin_headers)

    assert response.status_code == 422


def test_list_users_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.get("/api/v1/admin/users", headers=customer_headers)

    assert response.status_code == 403


def test_update_user_changes_fields(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/update/{target_user.id}",
        json={"first_name": "Updated"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["first_name"] == "Updated"


def test_update_user_can_change_status_and_type(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/update/{target_user.id}",
        json={"status": "suspended", "user_type": "private"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "suspended"

    db = SessionLocal()
    try:
        updated = db.get(User, target_user.id)
        assert updated is not None
        assert updated.user_type == UserType.PRIVATE
    finally:
        db.close()


def test_update_user_rejects_duplicate_email(
    client: TestClient, admin_headers: dict[str, str], target_user: User, conflict_user: User
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/update/{target_user.id}",
        json={"email": conflict_user.email},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_update_user_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/update/{uuid4()}",
        json={"first_name": "Nobody"},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_user_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], target_user: User
) -> None:
    response = client.patch(
        f"/api/v1/admin/users/update/{target_user.id}",
        json={"first_name": "Nope"},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_set_user_roles_assigns_roles(
    client: TestClient, admin_headers: dict[str, str], target_user: User, role: Role
) -> None:
    response = client.put(
        f"/api/v1/admin/users/update/{target_user.id}/roles",
        json={"role_ids": [str(role.id)]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert [r["id"] for r in body["roles"]] == [str(role.id)]


def test_set_user_roles_rejects_unknown_role_id(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.put(
        f"/api/v1/admin/users/update/{target_user.id}/roles",
        json={"role_ids": [str(uuid4())]},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_set_user_roles_returns_404_for_unknown_user(
    client: TestClient, admin_headers: dict[str, str], role: Role
) -> None:
    response = client.put(
        f"/api/v1/admin/users/update/{uuid4()}/roles",
        json={"role_ids": [str(role.id)]},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_set_user_roles_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], target_user: User, role: Role
) -> None:
    response = client.put(
        f"/api/v1/admin/users/update/{target_user.id}/roles",
        json={"role_ids": [str(role.id)]},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_update_user_image_uploads_and_replaces_previous(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    upload_dir = Path(get_settings().upload_dir)
    first_response = client.post(
        f"/api/v1/admin/users/update/{target_user.id}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=admin_headers,
    )
    assert first_response.status_code == 200
    first_url = first_response.json()["data"]["profile_image_url"]
    first_path = upload_dir / Path(first_url).name
    assert first_path.exists()

    second_response = client.post(
        f"/api/v1/admin/users/update/{target_user.id}/image",
        files={"image": ("second.png", b"second-bytes", "image/png")},
        headers=admin_headers,
    )
    assert second_response.status_code == 200
    second_url = second_response.json()["data"]["profile_image_url"]
    second_path = upload_dir / Path(second_url).name

    assert second_url != first_url
    assert not first_path.exists()

    second_path.unlink(missing_ok=True)


def test_update_user_image_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/admin/users/update/{uuid4()}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_user_image_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], target_user: User
) -> None:
    response = client.post(
        f"/api/v1/admin/users/update/{target_user.id}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_delete_user_soft_deletes_and_hides_from_reads(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    response = client.delete(f"/api/v1/admin/users/delete/{target_user.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["success"] is True

    get_response = client.get(f"/api/v1/admin/users/edit/{target_user.id}", headers=admin_headers)
    assert get_response.status_code == 404


def test_delete_user_allows_email_reuse(
    client: TestClient, admin_headers: dict[str, str], target_user: User
) -> None:
    delete_response = client.delete(
        f"/api/v1/admin/users/delete/{target_user.id}", headers=admin_headers
    )
    assert delete_response.status_code == 200

    create_response = client.post(
        "/api/v1/admin/users/create",
        json={
            "first_name": "Reused",
            "last_name": "Email",
            "email": TARGET_EMAIL,
            "password": "SomePassword123!",
        },
        headers=admin_headers,
    )

    assert create_response.status_code == 201
    _delete_user(UUID(create_response.json()["data"]["id"]))


def test_delete_user_rejects_deleting_self(
    client: TestClient, admin_headers: dict[str, str], admin_actor: User
) -> None:
    response = client.delete(f"/api/v1/admin/users/delete/{admin_actor.id}", headers=admin_headers)

    assert response.status_code == 422


def test_delete_user_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.delete(f"/api/v1/admin/users/delete/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_delete_user_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], target_user: User
) -> None:
    response = client.delete(
        f"/api/v1/admin/users/delete/{target_user.id}", headers=customer_headers
    )

    assert response.status_code == 403
