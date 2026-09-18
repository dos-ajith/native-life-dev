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
from app.models.setting import Setting
from app.models.user import User, UserStatus, UserType

ADMIN_EMAIL = "settings-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
CUSTOMER_EMAIL = "settings-integration-customer@example.com"
SETTING_KEY = "settings-integration.max_upload_mb"
CONFLICT_SETTING_KEY = "settings-integration.conflict"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
    db.commit()
    db.close()


def _delete_setting(setting_id: UUID) -> None:
    db = SessionLocal()
    db.execute(delete(Setting).where(Setting.id == setting_id))
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
def setting() -> Iterator[Setting]:
    db = SessionLocal()
    setting = Setting(key=SETTING_KEY, value="25")
    db.add(setting)
    db.commit()
    db.refresh(setting)
    try:
        yield setting
    finally:
        db.execute(delete(Setting).where(Setting.id == setting.id))
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


def test_create_setting_returns_created_setting(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/settings/create",
        json={"key": SETTING_KEY, "value": "25"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["key"] == SETTING_KEY
    assert body["value"] == "25"

    _delete_setting(UUID(body["id"]))


def test_create_setting_rejects_duplicate_key(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.post(
        "/api/v1/admin/settings/create",
        json={"key": SETTING_KEY, "value": "50"},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_setting_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        "/api/v1/admin/settings/create",
        json={"key": SETTING_KEY, "value": "25"},
    )

    assert response.status_code == 401


def test_create_setting_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/settings/create",
        json={"key": SETTING_KEY, "value": "25"},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_list_settings_returns_paginated_page(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.get("/api/v1/admin/settings?page=1&page_size=5", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 1


def test_get_setting_returns_setting(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.get(f"/api/v1/admin/settings/edit/{setting.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["key"] == SETTING_KEY


def test_get_setting_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(f"/api/v1/admin/settings/edit/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_get_setting_by_key_returns_setting(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.get(f"/api/v1/admin/settings/key/{SETTING_KEY}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(setting.id)


def test_get_setting_by_key_returns_404_for_unknown_key(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(
        "/api/v1/admin/settings/key/settings-integration.unknown", headers=admin_headers
    )

    assert response.status_code == 404


def test_update_setting_changes_value(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.patch(
        f"/api/v1/admin/settings/update/{setting.id}",
        json={"value": "50"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["value"] == "50"


def test_update_setting_rejects_duplicate_key(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    create_response = client.post(
        "/api/v1/admin/settings/create",
        json={"key": CONFLICT_SETTING_KEY, "value": "1"},
        headers=admin_headers,
    )
    conflict_id = create_response.json()["data"]["id"]

    response = client.patch(
        f"/api/v1/admin/settings/update/{conflict_id}",
        json={"key": SETTING_KEY},
        headers=admin_headers,
    )

    assert response.status_code == 422
    _delete_setting(UUID(conflict_id))


def test_delete_setting_removes_setting(
    client: TestClient, admin_headers: dict[str, str], setting: Setting
) -> None:
    response = client.delete(f"/api/v1/admin/settings/delete/{setting.id}", headers=admin_headers)

    assert response.status_code == 200

    get_response = client.get(f"/api/v1/admin/settings/edit/{setting.id}", headers=admin_headers)
    assert get_response.status_code == 404
