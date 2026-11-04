from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.permissions import RoleSlug
from app.main import app
from app.models.category import Category
from app.models.permission import Permission
from app.models.plugin import PluginBusinessType
from app.models.role import Role
from app.models.user import User
from app.plugins.errors import PluginError
from app.plugins.manifest import parse_manifest
from app.services.business_category_service import business_type_of, ordered_chain
from app.services.business_plugin_service import visible_capabilities
from tests.unit.plugins.conftest import manifest_toml

API = get_settings().api_v1_prefix
CAPABILITY = """
[[capabilities]]
key = "orders"
title = "Orders"
type = "menu"
path = "{path}"
permission = "{permission}"
"""


def _manifest(path: str = "/businesses/{business_id}/orders", permission: str = "") -> bytes:
    permission = permission or "plugin.catalog.item.view"
    return manifest_toml(
        "catalog", extra=CAPABILITY.format(path=path, permission=permission)
    ).encode()


def test_capabilities_are_validated() -> None:
    manifest = parse_manifest(_manifest())
    assert [capability.key for capability in manifest.capabilities] == ["orders"]
    for bad_path in ("orders", "/businesses/{owner_id}", "/../admin", "/a//b", "/Upper"):
        with pytest.raises(PluginError, match="Capability path"):
            parse_manifest(_manifest(path=bad_path))
    with pytest.raises(PluginError, match="does not declare"):
        parse_manifest(_manifest(permission="plugin.catalog.secret.view"))
    duplicated = manifest_toml(
        "catalog",
        extra=CAPABILITY.format(path="/a", permission="plugin.catalog.item.view") * 2,
    )
    with pytest.raises(PluginError, match="more than once"):
        parse_manifest(duplicated.encode())


def _user(*permission_names: str, slug: str = RoleSlug.INDIVIDUAL_USER) -> User:
    role = Role(slug=slug, name=slug, permissions=[Permission(name=n) for n in permission_names])
    return User(roles=[role])


def test_capabilities_are_filtered_by_the_viewer_permissions() -> None:
    manifest = parse_manifest(_manifest())
    assert visible_capabilities(manifest, _user()) == []
    assert len(visible_capabilities(manifest, _user("plugin.catalog.item.view"))) == 1
    assert len(visible_capabilities(manifest, _user(slug=RoleSlug.SUPER_ADMIN))) == 1


def _category(slug: str, parent: Category | None) -> Category:
    return Category(id=uuid4(), slug=slug, name=slug, parent_id=parent.id if parent else None)


def test_chain_is_ordered_from_root_and_business_type_is_derived() -> None:
    root = _category("business", None)
    service = _category("business-service", root)
    hotel = _category("business-service-hotel", service)
    chain = ordered_chain([hotel, root, service], hotel.id)
    assert [category.slug for category in chain] == [
        "business",
        "business-service",
        "business-service-hotel",
    ]
    assert business_type_of(chain) == PluginBusinessType.SERVICE
    deals = _category("deals", None)
    assert business_type_of(ordered_chain([deals], deals.id)) is None
    assert business_type_of([]) is None


@pytest.mark.parametrize(
    ("method", "suffix"),
    [
        ("GET", "/capabilities"),
        ("GET", "/plugins/available"),
        ("POST", "/plugins/hello"),
        ("DELETE", "/plugins/hello"),
    ],
)
def test_business_plugin_endpoints_require_authentication(method: str, suffix: str) -> None:
    response = TestClient(app).request(method, f"{API}/me/businesses/{uuid4()}{suffix}")
    assert response.status_code == 401
    assert response.json()["success"] is False
