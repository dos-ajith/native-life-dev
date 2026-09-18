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
from app.models.page import Page, PageStatus
from app.models.user import User, UserStatus, UserType

ADMIN_EMAIL = "pages-integration-admin@example.com"
ADMIN_PASSWORD = "correct-horse-battery-staple"
CUSTOMER_EMAIL = "pages-integration-customer@example.com"
PAGE_TITLE = "Pages Integration About Us"
CONFLICT_PAGE_TITLE = "Pages Integration Conflict"


def _delete_active_token(token: str) -> None:
    payload = decode_access_token(token, get_settings())
    db = SessionLocal()
    db.execute(delete(ActiveToken).where(ActiveToken.jti == payload["jti"]))
    db.commit()
    db.close()


def _delete_page(page_id: UUID) -> None:
    db = SessionLocal()
    db.execute(delete(Page).where(Page.id == page_id))
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
def page(admin_actor: User) -> Iterator[Page]:
    db = SessionLocal()
    page = Page(
        title=PAGE_TITLE,
        slug="pages-integration-about-us",
        content="Some content",
        status=PageStatus.DRAFT,
        created_by=admin_actor.id,
        updated_by=admin_actor.id,
    )
    db.add(page)
    db.commit()
    db.refresh(page)
    try:
        yield page
    finally:
        db.execute(delete(Page).where(Page.id == page.id))
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


def test_create_page_returns_created_page(
    client: TestClient, admin_headers: dict[str, str], admin_actor: User
) -> None:
    response = client.post(
        "/api/v1/admin/pages/create",
        data={"title": PAGE_TITLE, "content": "Some content"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["title"] == PAGE_TITLE
    assert body["slug"] == "pages-integration-about-us"
    assert body["status"] == "draft"
    assert body["image_url"] is None
    assert body["published_at"] is None
    assert body["created_by"] == str(admin_actor.id)
    assert body["updated_by"] == str(admin_actor.id)

    _delete_page(UUID(body["id"]))


def test_create_page_with_image_uploads_it(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    upload_dir = Path(get_settings().upload_dir)
    response = client.post(
        "/api/v1/admin/pages/create",
        data={"title": "Pages Integration With Image"},
        files={"image": ("cover.png", b"cover-bytes", "image/png")},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["image_url"] is not None
    image_path = upload_dir / Path(body["image_url"]).name
    assert image_path.exists()

    image_path.unlink(missing_ok=True)
    _delete_page(UUID(body["id"]))


def test_create_page_sets_published_at_when_published(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/pages/create",
        data={"title": CONFLICT_PAGE_TITLE, "status": "published"},
        headers=admin_headers,
    )

    assert response.status_code == 201
    body = response.json()["data"]
    assert body["status"] == "published"
    assert body["published_at"] is not None

    _delete_page(UUID(body["id"]))


def test_create_page_rejects_duplicate_slug(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.post(
        "/api/v1/admin/pages/create",
        data={"title": PAGE_TITLE},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_page_rejects_blank_title(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/pages/create",
        data={"title": "   "},
        headers=admin_headers,
    )

    assert response.status_code == 422


def test_create_page_rejects_missing_token(client: TestClient) -> None:
    response = client.post("/api/v1/admin/pages/create", data={"title": PAGE_TITLE})

    assert response.status_code == 401


def test_create_page_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/admin/pages/create", data={"title": PAGE_TITLE}, headers=customer_headers
    )

    assert response.status_code == 403


def test_list_pages_returns_paginated_page(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.get("/api/v1/admin/pages?page=1&page_size=5", headers=admin_headers)

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["page"] == 1
    assert data["page_size"] == 5
    assert data["total"] >= 1


def test_get_page_returns_page(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.get(f"/api/v1/admin/pages/edit/{page.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["title"] == PAGE_TITLE


def test_get_page_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(f"/api/v1/admin/pages/edit/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404


def test_get_page_by_slug_returns_page(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.get(f"/api/v1/admin/pages/slug/{page.slug}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["data"]["id"] == str(page.id)


def test_get_page_by_slug_returns_404_for_unknown_slug(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.get(
        "/api/v1/admin/pages/slug/pages-integration-unknown", headers=admin_headers
    )

    assert response.status_code == 404


def test_update_page_changes_content(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.patch(
        f"/api/v1/admin/pages/update/{page.id}",
        data={"content": "Updated content"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["data"]["content"] == "Updated content"


def test_update_page_with_image_uploads_it(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    upload_dir = Path(get_settings().upload_dir)
    response = client.patch(
        f"/api/v1/admin/pages/update/{page.id}",
        data={"content": "Updated content"},
        files={"image": ("cover.png", b"cover-bytes", "image/png")},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["image_url"] is not None
    image_path = upload_dir / Path(body["image_url"]).name
    assert image_path.exists()

    image_path.unlink(missing_ok=True)


def test_update_page_sets_published_at_on_publish(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.patch(
        f"/api/v1/admin/pages/update/{page.id}",
        data={"status": "published"},
        headers=admin_headers,
    )

    assert response.status_code == 200
    body = response.json()["data"]
    assert body["status"] == "published"
    assert body["published_at"] is not None


def test_delete_page_removes_page(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    response = client.delete(f"/api/v1/admin/pages/delete/{page.id}", headers=admin_headers)

    assert response.status_code == 200

    get_response = client.get(f"/api/v1/admin/pages/edit/{page.id}", headers=admin_headers)
    assert get_response.status_code == 404


def test_update_page_image_uploads_and_replaces_previous(
    client: TestClient, admin_headers: dict[str, str], page: Page
) -> None:
    upload_dir = Path(get_settings().upload_dir)
    first_response = client.post(
        f"/api/v1/admin/pages/update/{page.id}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=admin_headers,
    )
    assert first_response.status_code == 200
    first_url = first_response.json()["data"]["image_url"]
    first_path = upload_dir / Path(first_url).name
    assert first_path.exists()

    second_response = client.post(
        f"/api/v1/admin/pages/update/{page.id}/image",
        files={"image": ("second.png", b"second-bytes", "image/png")},
        headers=admin_headers,
    )
    assert second_response.status_code == 200
    second_url = second_response.json()["data"]["image_url"]
    second_path = upload_dir / Path(second_url).name

    assert second_url != first_url
    assert not first_path.exists()

    second_path.unlink(missing_ok=True)


def test_update_page_image_returns_404_for_unknown_id(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    response = client.post(
        f"/api/v1/admin/pages/update/{uuid4()}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=admin_headers,
    )

    assert response.status_code == 404


def test_update_page_image_rejects_non_admin(
    client: TestClient, customer_headers: dict[str, str], page: Page
) -> None:
    response = client.post(
        f"/api/v1/admin/pages/update/{page.id}/image",
        files={"image": ("first.png", b"first-bytes", "image/png")},
        headers=customer_headers,
    )

    assert response.status_code == 403
