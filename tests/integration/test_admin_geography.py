import io
import zipfile
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.jwt import decode_access_token
from app.core.security import hash_password
from app.models.active_token import ActiveToken
from app.models.user import User, UserStatus, UserType

ADMIN_EMAIL = "geography-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
CUSTOMER_EMAIL = "geography-integration-customer@example.com"
IMPORT_URL = "/api/v1/admin/geography/import"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
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


def _zip_bytes(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_import_geography_rejects_missing_token(client: TestClient) -> None:
    response = client.post(
        IMPORT_URL,
        files={"file": ("boundary.zip", _zip_bytes({"a.txt": "x"}), "application/zip")},
    )

    assert response.status_code == 401


def test_import_geography_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        IMPORT_URL,
        files={"file": ("boundary.zip", _zip_bytes({"a.txt": "x"}), "application/zip")},
        headers=customer_headers,
    )

    assert response.status_code == 403


def test_import_geography_rejects_non_zip_file(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        IMPORT_URL,
        files={"file": ("boundary.rar", b"not a zip", "application/octet-stream")},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_import_geography_rejects_invalid_zip_content(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        IMPORT_URL,
        files={"file": ("boundary.zip", b"this is not a real zip archive", "application/zip")},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_import_geography_rejects_zip_missing_required_layers(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        IMPORT_URL,
        files={
            "file": (
                "boundary.zip",
                _zip_bytes({"README.txt": "no shapefiles here"}),
                "application/zip",
            )
        },
        headers=admin_headers,
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
