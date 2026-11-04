from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.permissions import PermissionName, RoleSlug
from app.main import app
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from scripts.seed import ALL_PERMISSION_NAMES, NATIVE_ADMIN_PERMISSIONS, ROLE_DEFINITIONS
from tests.unit.plugins.conftest import individual_user, override_auth, super_admin

API = get_settings().api_v1_prefix
ADMIN_ENDPOINTS = [
    ("GET", f"{API}/admin/plugins"),
    ("GET", f"{API}/admin/plugins/load-report"),
    ("GET", f"{API}/admin/plugins/hello"),
    ("POST", f"{API}/admin/plugins/hello/enable"),
    ("POST", f"{API}/admin/plugins/hello/disable"),
]


@pytest.fixture(autouse=True)
def clear_overrides() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


def verified_business_provider() -> User:
    role = Role(
        slug=RoleSlug.BUSINESS_SERVICE_PROVIDER,
        name="Business / Service Provider",
        permissions=[Permission(name=PermissionName.BUSINESS_CREATE)],
    )
    return User(roles=[role])


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
def test_anonymous_requests_are_rejected_with_401(method: str, path: str) -> None:
    response = TestClient(app).request(method, path)
    assert response.status_code == 401
    assert response.json()["success"] is False


@pytest.mark.parametrize(("method", "path"), ADMIN_ENDPOINTS)
@pytest.mark.parametrize("make_user", [individual_user, verified_business_provider])
def test_users_without_plugin_permissions_are_rejected_with_403(
    method: str, path: str, make_user: object
) -> None:
    assert callable(make_user)
    override_auth(app, make_user())
    response = TestClient(app).request(method, path)
    assert response.status_code == 403
    assert response.json()["success"] is False


def test_super_admin_can_read_the_load_report_without_plugins() -> None:
    override_auth(app, super_admin())
    response = TestClient(app).get(f"{API}/admin/plugins/load-report")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Plugin load report retrieved",
        "data": [],
    }


def test_plugin_management_permissions_are_seeded_for_super_admin_only() -> None:
    plugin_permissions = {PermissionName.PLUGIN_VIEW, PermissionName.PLUGIN_MANAGE}
    assert plugin_permissions <= set(ALL_PERMISSION_NAMES)
    assert ROLE_DEFINITIONS[RoleSlug.SUPER_ADMIN][1] == ALL_PERMISSION_NAMES
    assert not plugin_permissions & set(NATIVE_ADMIN_PERMISSIONS)
    for slug, (_, permissions) in ROLE_DEFINITIONS.items():
        if slug != RoleSlug.SUPER_ADMIN:
            assert not plugin_permissions & set(permissions), slug
