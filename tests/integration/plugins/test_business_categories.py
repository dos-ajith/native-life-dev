import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.activity_actions import ActivityAction
from app.core.database import SessionLocal
from app.core.exceptions import BusinessRuleError
from app.models.activity_log import ActivityLog
from app.models.category import Category, CategoryStatus
from app.services.business_category_service import BusinessCategoryService
from tests.integration.conftest import API
from tests.integration.plugins.conftest import (
    ActorFactory,
    PluginWorkspace,
    add_category,
    category_by_slug,
    plugin_manifest,
)

CORE_SLUGS = ("business", "business-product", "business-service")


def _seed() -> list[str]:
    with SessionLocal() as session:
        return [category.slug for category in BusinessCategoryService(session).seed()]


def _category_count() -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(Category)) or 0


def test_seeding_creates_the_core_business_tree_once() -> None:
    existing = add_category("Deals", None, slug="deals")
    created = _seed()
    assert sorted(created) == sorted(CORE_SLUGS)
    root = category_by_slug("business")
    product = category_by_slug("business-product")
    service = category_by_slug("business-service")
    assert root.parent_id is None and root.name == "Business"
    assert product.parent_id == root.id and product.name == "Product"
    assert service.parent_id == root.id and service.name == "Service"
    assert all(c.status == CategoryStatus.PUBLISHED and c.is_active for c in (root, product))
    assert _seed() == []
    assert _category_count() == 4
    assert category_by_slug("business").id == root.id
    assert category_by_slug("deals").id == existing.id
    with SessionLocal() as session:
        logs = session.scalar(
            select(func.count())
            .select_from(ActivityLog)
            .where(ActivityLog.action == ActivityAction.CATEGORY_CREATED)
        )
    assert logs == 3


def test_seeding_refuses_to_duplicate_or_rename_a_conflicting_category() -> None:
    add_category("Business", None, slug="business-hand-made")
    with pytest.raises(BusinessRuleError, match="expected slug 'business'"):
        _seed()
    assert _category_count() == 1
    assert category_by_slug("business-hand-made").name == "Business"


def test_seeding_refuses_a_misplaced_core_slug() -> None:
    add_category("Deals", None, slug="deals")
    add_category("Business", "deals", slug="business")
    with pytest.raises(BusinessRuleError):
        _seed()
    assert _category_count() == 2


def _root_names(client: TestClient, headers: dict[str, str]) -> list[str]:
    response = client.get(f"{API}/categories", headers=headers)
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["data"]["items"]]


def test_listing_orders_by_sort_order_then_name(client: TestClient, actor: ActorFactory) -> None:
    admin = actor("super_admin")
    zeta = add_category("Zeta", None)
    alpha = add_category("Alpha", None)
    mid = add_category("Mid", None)
    assert _root_names(client, admin.headers) == ["Alpha", "Mid", "Zeta"]
    for category, order in ((alpha, 10), (mid, 5)):
        response = client.patch(
            f"{API}/categories/{category.id}", json={"sort_order": order}, headers=admin.headers
        )
        assert response.status_code == 200, response.text
        assert response.json()["data"]["sort_order"] == order
    assert _root_names(client, admin.headers) == ["Zeta", "Mid", "Alpha"]
    assert category_by_slug(zeta.slug).sort_order == 0


def test_sort_order_must_be_non_negative(client: TestClient, actor: ActorFactory) -> None:
    admin = actor("super_admin")
    category = add_category("Alpha", None)
    response = client.patch(
        f"{API}/categories/{category.id}", json={"sort_order": -1}, headers=admin.headers
    )
    assert response.status_code == 422


def test_category_bound_to_a_plugin_cannot_be_deleted(
    client: TestClient, actor: ActorFactory, workspace: PluginWorkspace
) -> None:
    admin = actor("super_admin")
    workspace.write(
        "hotel",
        plugin_manifest(
            "hotel",
            categories='[{ slug = "business-service-hotel", name = "Hotel", '
            'parent = "business-service", bind = true }]',
        ),
    )
    assert workspace.apply()["hotel"].outcome == "installed"
    hotel = category_by_slug("business-service-hotel")
    response = client.delete(f"{API}/categories/{hotel.id}", headers=admin.headers)
    assert response.status_code == 422
    assert "used by a business plugin" in response.json()["message"]
