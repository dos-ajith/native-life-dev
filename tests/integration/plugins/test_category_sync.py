import pytest
from sqlalchemy import func, select

from app.core.activity_actions import ActivityAction
from app.core.database import SessionLocal
from app.models.activity_log import ActivityLog
from app.models.category import Category, CategoryStatus
from app.models.plugin import Plugin
from app.models.plugin_category_binding import PluginCategoryBinding, PluginCategoryOwnership
from app.models.plugin_installation import PluginInstallation, PluginInstallationStatus
from app.services.business_category_service import BusinessCategoryService
from tests.integration.plugins.conftest import (
    PluginWorkspace,
    add_category,
    category_by_slug,
    plugin_manifest,
)

HOTEL = (
    '{ slug = "business-service-hotel", name = "Hotel", parent = "business-service", '
    "bind = true, include_descendants = true }"
)
RESORT = (
    '{ slug = "business-service-hotel-resort", name = "Resort", parent = "business-service-hotel" }'
)


def _bindings(key: str) -> dict[str, PluginCategoryBinding]:
    with SessionLocal() as session:
        rows = session.execute(
            select(PluginCategoryBinding, Category.slug)
            .join(Plugin, Plugin.id == PluginCategoryBinding.plugin_id)
            .join(Category, Category.id == PluginCategoryBinding.category_id)
            .where(Plugin.key == key)
        ).all()
        for binding, _ in rows:
            session.expunge(binding)
        return {slug: binding for binding, slug in rows}


def _count(model: type, *conditions: object) -> int:
    with SessionLocal() as session:
        return session.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def _seed_core() -> None:
    with SessionLocal() as session:
        BusinessCategoryService(session).seed()


def test_apply_creates_declared_categories_and_bindings(workspace: PluginWorkspace) -> None:
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}, {RESORT}]"))
    assert workspace.apply()["hotel"].outcome == "installed"
    hotel = category_by_slug("business-service-hotel")
    resort = category_by_slug("business-service-hotel-resort")
    assert hotel.parent_id == category_by_slug("business-service").id
    assert resort.parent_id == hotel.id
    assert hotel.status == CategoryStatus.PUBLISHED and hotel.is_active
    assert hotel.created_by is None
    bindings = _bindings("hotel")
    assert set(bindings) == {"business-service-hotel", "business-service-hotel-resort"}
    hotel_binding = bindings["business-service-hotel"]
    assert hotel_binding.ownership == PluginCategoryOwnership.CREATED
    assert hotel_binding.applies_to_businesses and hotel_binding.include_descendants
    assert not bindings["business-service-hotel-resort"].applies_to_businesses
    assert _count(ActivityLog, ActivityLog.action == ActivityAction.PLUGIN_CATEGORIES_SYNCED) == 1
    assert _count(ActivityLog, ActivityLog.action == ActivityAction.CATEGORY_CREATED) == 5


def test_reapplying_is_idempotent(workspace: PluginWorkspace) -> None:
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}]"))
    workspace.apply()
    categories, bindings, logs = (
        _count(Category),
        _count(PluginCategoryBinding),
        _count(ActivityLog),
    )
    assert workspace.apply()["hotel"].outcome == "unchanged"
    assert (_count(Category), _count(PluginCategoryBinding), _count(ActivityLog)) == (
        categories,
        bindings,
        logs,
    )


def test_existing_published_category_is_adopted_without_changes(
    workspace: PluginWorkspace,
) -> None:
    _seed_core()
    existing = add_category("Hotels & Stays", "business-service", slug="business-service-hotel")
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}]"))
    assert workspace.apply()["hotel"].outcome == "installed"
    adopted = category_by_slug("business-service-hotel")
    assert adopted.id == existing.id
    assert adopted.name == "Hotels & Stays"
    assert _bindings("hotel")["business-service-hotel"].ownership == PluginCategoryOwnership.ADOPTED


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ("pending", "is pending"),
        ("rejected", "is rejected"),
        ("outside", "outside the 'business-service' category tree"),
        ("name_clash", "A category named 'Hotel' already exists"),
    ],
)
def test_conflicts_fail_the_apply_without_partial_changes(
    workspace: PluginWorkspace, setup: str, expected: str
) -> None:
    _seed_core()
    if setup == "pending":
        add_category("Hotel", "business-service", "business-service-hotel", CategoryStatus.PENDING)
    elif setup == "rejected":
        add_category("Hotel", "business-service", "business-service-hotel", CategoryStatus.REJECTED)
    elif setup == "outside":
        add_category("Deals", None, slug="deals")
        add_category("Hotel", "deals", slug="business-service-hotel")
    else:
        add_category("Hotel", "business-service", slug="hotel-by-admin")
    before = _count(Category)
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}, {RESORT}]"))
    result = workspace.apply()["hotel"]
    assert result.outcome == "failed"
    assert result.message is not None and expected in result.message
    assert _count(Category) == before
    assert _count(Plugin) == 0
    assert _count(PluginCategoryBinding) == 0
    assert (
        _count(PluginInstallation, PluginInstallation.status == PluginInstallationStatus.FAILED)
        == 1
    )


def test_removed_declarations_keep_categories_and_history(workspace: PluginWorkspace) -> None:
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}, {RESORT}]"))
    workspace.apply()
    workspace.write("hotel", plugin_manifest("hotel", version="1.1.0", categories=f"[{HOTEL}]"))
    assert workspace.apply()["hotel"].outcome == "upgraded"
    bindings = _bindings("hotel")
    assert bindings["business-service-hotel-resort"].removed_at is not None
    assert bindings["business-service-hotel"].removed_at is None
    assert category_by_slug("business-service-hotel-resort").status == CategoryStatus.PUBLISHED
    workspace.write(
        "hotel", plugin_manifest("hotel", version="1.2.0", categories=f"[{HOTEL}, {RESORT}]")
    )
    workspace.apply()
    assert _bindings("hotel")["business-service-hotel-resort"].removed_at is None


def test_plugins_can_share_a_category(workspace: PluginWorkspace) -> None:
    workspace.write("hotel", plugin_manifest("hotel", categories=f"[{HOTEL}]"))
    workspace.write("booking", plugin_manifest("booking", categories=f"[{HOTEL}]"))
    results = workspace.apply()
    assert results["booking"].outcome == "installed" and results["hotel"].outcome == "installed"
    ownerships = {
        _bindings(key)["business-service-hotel"].ownership for key in ("booking", "hotel")
    }
    assert ownerships == {PluginCategoryOwnership.CREATED, PluginCategoryOwnership.ADOPTED}
    assert _count(Category, Category.slug == "business-service-hotel") == 1


def test_product_plugin_cannot_claim_service_categories(workspace: PluginWorkspace) -> None:
    workspace.write(
        "shop", plugin_manifest("shop", business_type="product", categories=f"[{HOTEL}]")
    )
    result = workspace.apply()
    assert result[None].outcome == "failed"
    assert result[None].message is not None and "business-product-" in result[None].message
