from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.activity_actions import ActivityAction
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.exceptions import AppError
from app.core.openapi_tags import OPENAPI_TAGS
from app.main import app_error_handler, http_error_handler
from app.models.activity_log import ActivityLog
from app.models.business import Business, BusinessStatus
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.plugin import Plugin, PluginStatus
from app.plugins.discovery import load_candidate
from app.plugins.loader import load_plugin
from app.plugins.mounting import mount_plugin
from tests.integration.conftest import API
from tests.integration.plugins.conftest import (
    Actor,
    ActorFactory,
    PluginWorkspace,
    add_business,
    add_category,
    plugin_manifest,
    set_plugin_status,
)

HOTEL = (
    '{ slug = "business-service-hotel", name = "Hotel", parent = "business-service", '
    "bind = true, include_descendants = true }"
)
SPA = '{ slug = "business-service-spa", name = "Spa", parent = "business-service", bind = true }'
HOTEL_CAPABILITIES = """
[[capabilities]]
key = "rooms"
title = "Rooms"
type = "menu"
path = "/businesses/{business_id}/rooms"
permission = "plugin.hotel.room.view"
"""
REFERENCE_ROOT = Path(__file__).resolve().parents[3] / "plugins" / "_reference" / "hello"

UseRegistry = Callable[..., None]


@pytest.fixture
def plugins(workspace: PluginWorkspace, use_registry: UseRegistry) -> PluginWorkspace:
    workspace.write(
        "hotel",
        plugin_manifest(
            "hotel",
            categories=f"[{HOTEL}]",
            capabilities=HOTEL_CAPABILITIES,
            permissions=("plugin.hotel.room.view",),
        ),
    )
    workspace.write("spa", plugin_manifest("spa", categories=f"[{SPA}]"))
    results = workspace.apply()
    assert {key: result.outcome for key, result in results.items()} == {
        "hotel": "installed",
        "spa": "installed",
    }
    for key in ("hotel", "spa"):
        set_plugin_status(key, PluginStatus.ENABLED)
    use_registry("hotel", "spa")
    return workspace


def _path(business: Business, suffix: str) -> str:
    return f"{API}/me/businesses/{business.id}{suffix}"


def _enable(client: TestClient, who: Actor, business: Business, key: str = "hotel") -> Any:
    return client.post(_path(business, f"/plugins/{key}"), headers=who.headers)


def _disable(client: TestClient, who: Actor, business: Business, key: str = "hotel") -> Any:
    return client.delete(_path(business, f"/plugins/{key}"), headers=who.headers)


def _business_plugin_rows() -> list[tuple[str, BusinessPluginStatus]]:
    with SessionLocal() as session:
        rows = session.execute(
            select(Plugin.key, BusinessPlugin.status).join(
                Plugin, Plugin.id == BusinessPlugin.plugin_id
            )
        ).all()
        return [(key, status) for key, status in rows]


def _log_count(action: str) -> int:
    with SessionLocal() as session:
        return (
            session.scalar(
                select(func.count()).select_from(ActivityLog).where(ActivityLog.action == action)
            )
            or 0
        )


def test_owner_enables_and_disables_idempotently(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    business = add_business(owner.user, "business-service-hotel")
    first = _enable(client, owner, business)
    assert first.status_code == 200, first.text
    assert first.json()["data"]["status"] == "active"
    assert first.json()["data"]["enabled_by"] == str(owner.user.id)
    assert _enable(client, owner, business).status_code == 200
    assert _business_plugin_rows() == [("hotel", BusinessPluginStatus.ACTIVE)]
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_ENABLED) == 1
    disabled = _disable(client, owner, business)
    assert disabled.status_code == 200 and disabled.json()["data"]["status"] == "disabled"
    assert _disable(client, owner, business).status_code == 200
    assert _log_count(ActivityAction.BUSINESS_PLUGIN_DISABLED) == 1
    assert _enable(client, owner, business).status_code == 200
    assert _business_plugin_rows() == [("hotel", BusinessPluginStatus.ACTIVE)]
    with SessionLocal() as session:
        statuses = session.scalars(select(Plugin.status)).all()
    assert set(statuses) == {PluginStatus.ENABLED}


def test_disabling_a_plugin_that_was_never_enabled_is_a_no_op(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    business = add_business(owner.user, "business-service-hotel")
    response = _disable(client, owner, business)
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "disabled"
    assert _business_plugin_rows() == []


def test_capabilities_and_available_plugins(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    admin = actor("super_admin")
    business = add_business(owner.user, "business-service-hotel")
    available = client.get(_path(business, "/plugins/available"), headers=owner.headers)
    assert available.status_code == 200
    assert [(p["key"], p["enabled_for_business"]) for p in available.json()["data"]] == [
        ("hotel", False)
    ]
    _enable(client, owner, business)
    owner_view = client.get(_path(business, "/capabilities"), headers=owner.headers).json()["data"]
    assert owner_view["business_type"] == "service"
    assert [c["slug"] for c in owner_view["categories"]] == [
        "business-service",
        "business-service-hotel",
    ]
    assert owner_view["available_plugins"] == []
    assert [p["key"] for p in owner_view["enabled_plugins"]] == ["hotel"]
    assert owner_view["enabled_plugins"][0]["capabilities"] == []
    admin_view = client.get(_path(business, "/capabilities"), headers=admin.headers).json()["data"]
    assert admin_view["enabled_plugins"][0]["capabilities"] == [
        {
            "key": "rooms",
            "title": "Rooms",
            "type": "menu",
            "path": f"{get_settings().api_v1_prefix}/plugins/hotel/businesses/{business.id}/rooms",
        }
    ]


def test_descendant_categories_inherit_compatibility(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    add_category("Resort", "business-service-hotel", slug="business-service-hotel-resort")
    add_category("Day Spa", "business-service-spa", slug="business-service-spa-day")
    resort = add_business(owner.user, "business-service-hotel-resort")
    day_spa = add_business(owner.user, "business-service-spa-day")
    assert _enable(client, owner, resort).status_code == 200
    incompatible = _enable(client, owner, day_spa, "spa")
    assert incompatible.status_code == 422
    assert "not available for this business" in incompatible.json()["message"]


@pytest.mark.parametrize("category", ["business-product", None, "lost-found"])
def test_incompatible_categories_are_rejected(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace, category: str | None
) -> None:
    owner = actor("provider")
    if category == "lost-found":
        add_category("Lost & Found", None, slug="lost-found")
    business = add_business(owner.user, category)
    assert _enable(client, owner, business).status_code == 422
    view = client.get(_path(business, "/capabilities"), headers=owner.headers).json()["data"]
    assert view["available_plugins"] == [] and view["enabled_plugins"] == []


def test_other_owners_cannot_touch_a_business(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    intruder = actor("provider")
    business = add_business(owner.user, "business-service-hotel")
    for response in (
        _enable(client, intruder, business),
        _disable(client, intruder, business),
        client.get(_path(business, "/capabilities"), headers=intruder.headers),
        client.get(_path(business, "/plugins/available"), headers=intruder.headers),
    ):
        assert response.status_code == 403, response.text
    assert _business_plugin_rows() == []


def test_anonymous_requests_are_rejected(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    business = add_business(owner.user, "business-service-hotel")
    for method, suffix in (
        ("GET", "/capabilities"),
        ("GET", "/plugins/available"),
        ("POST", "/plugins/hotel"),
        ("DELETE", "/plugins/hotel"),
    ):
        assert client.request(method, _path(business, suffix)).status_code == 401


def test_missing_and_deleted_businesses_return_404(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    deleted = add_business(owner.user, "business-service-hotel", deleted=True)
    assert _enable(client, owner, deleted).status_code == 404
    missing = f"{API}/me/businesses/00000000-0000-0000-0000-000000000000/capabilities"
    assert client.get(missing, headers=owner.headers).status_code == 404


def test_unknown_unloaded_and_globally_disabled_plugins_are_not_available(
    client: TestClient,
    actor: ActorFactory,
    plugins: PluginWorkspace,
    use_registry: UseRegistry,
) -> None:
    owner = actor("provider")
    business = add_business(owner.user, "business-service-hotel")
    assert _enable(client, owner, business, "nope").status_code == 404
    set_plugin_status("hotel", PluginStatus.DISABLED)
    assert _enable(client, owner, business).status_code == 404
    set_plugin_status("hotel", PluginStatus.ENABLED)
    use_registry("spa")
    assert _enable(client, owner, business).status_code == 404
    use_registry("hotel", "spa")
    assert _enable(client, owner, business).status_code == 200
    set_plugin_status("hotel", PluginStatus.DISABLED)
    view = client.get(_path(business, "/capabilities"), headers=owner.headers).json()["data"]
    assert view["enabled_plugins"] == [] and view["available_plugins"] == []
    assert _business_plugin_rows() == [("hotel", BusinessPluginStatus.ACTIVE)]
    assert _disable(client, owner, business).status_code == 200


def test_verification_and_status_rules_are_enforced(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    pending = actor("pending_provider")
    pending_business = add_business(pending.user, "business-service-hotel")
    response = _enable(client, pending, pending_business)
    assert response.status_code == 403
    assert "must be approved" in response.json()["message"]
    individual = actor("individual")
    individual_business = add_business(individual.user, "business-service-hotel")
    assert _enable(client, individual, individual_business).status_code == 403
    owner = actor("provider")
    inactive = add_business(owner.user, "business-service-hotel", status=BusinessStatus.INACTIVE)
    assert _enable(client, owner, inactive).status_code == 422


def test_super_admin_can_manage_any_business(
    client: TestClient, actor: ActorFactory, plugins: PluginWorkspace
) -> None:
    owner = actor("provider")
    admin = actor("super_admin")
    business = add_business(owner.user, "business-service-hotel")
    response = _enable(client, admin, business)
    assert response.status_code == 200
    assert response.json()["data"]["enabled_by"] == str(admin.user.id)


def _reference_app() -> FastAPI:
    application = FastAPI(openapi_tags=OPENAPI_TAGS)
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    application.include_router(api_router, prefix=API)
    mount_plugin(application, load_plugin(load_candidate(REFERENCE_ROOT)), API)
    return application


def test_business_scoped_plugin_route_requires_an_active_association(
    client: TestClient,
    actor: ActorFactory,
    workspace: PluginWorkspace,
    use_registry: UseRegistry,
) -> None:
    candidate = load_candidate(REFERENCE_ROOT)
    reference = PluginWorkspace(REFERENCE_ROOT.parent)
    results = reference.apply("hello")
    assert results["hello"].outcome == "installed", results["hello"].message
    set_plugin_status("hello", PluginStatus.ENABLED)
    use_registry("hello")
    owner = actor("provider")
    admin = actor("super_admin")
    business = add_business(owner.user, "business-service-reference")
    plugin_client = TestClient(_reference_app())
    greeting = f"{API}/plugins/hello/businesses/{business.id}/greeting"
    assert plugin_client.get(greeting, headers=admin.headers).status_code == 403
    assert _enable(client, owner, business, "hello").status_code == 200
    response = plugin_client.get(greeting, headers=admin.headers)
    assert response.status_code == 200, response.text
    assert response.json()["data"]["business_id"] == str(business.id)
    assert plugin_client.get(greeting, headers=owner.headers).status_code == 403
    other_owner = actor("provider")
    assert plugin_client.get(greeting, headers=other_owner.headers).status_code == 403
    _disable(client, owner, business, "hello")
    assert plugin_client.get(greeting, headers=admin.headers).status_code == 403
    set_plugin_status("hello", PluginStatus.DISABLED)
    assert plugin_client.get(greeting, headers=admin.headers).status_code == 404
    assert str(candidate.manifest.version) == "1.1.0"
