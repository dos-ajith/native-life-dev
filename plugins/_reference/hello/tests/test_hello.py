from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_active_user
from app.core.exceptions import AppError
from app.core.permissions import RoleSlug
from app.main import app_error_handler
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User
from app.plugins.boundaries import find_boundary_violations
from app.plugins.context import PluginContext
from app.plugins.discovery import load_candidate
from plugins._reference.hello.messages import HelloMessages
from plugins._reference.hello.permissions import HelloPermission
from plugins._reference.hello.plugin import register

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def _app_with(user: User) -> FastAPI:
    context = PluginContext(load_candidate(PLUGIN_ROOT).manifest)
    register(context)
    application = FastAPI()
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    for router in context.close().routers:
        application.include_router(router)
    application.dependency_overrides[get_current_active_user] = lambda: user
    return application


def test_manifest_declares_a_harmless_service_plugin() -> None:
    manifest = load_candidate(PLUGIN_ROOT).manifest
    assert manifest.key == "hello"
    assert manifest.dependencies == ()
    assert [category.slug for category in manifest.categories] == ["business-service-reference"]
    assert manifest.categories[0].bind and manifest.categories[0].include_descendants
    assert manifest.database.migrations is False
    assert set(manifest.permissions) == {HelloPermission.GREETING_VIEW}


def test_source_only_imports_the_sdk_from_the_core() -> None:
    assert find_boundary_violations(PLUGIN_ROOT) == []


def test_register_contributes_one_router_and_no_models() -> None:
    context = PluginContext(load_candidate(PLUGIN_ROOT).manifest)
    register(context)
    contribution = context.close()
    routes = contribution.routers[0].routes
    assert [route.path for route in routes if isinstance(route, APIRoute)] == [
        "/greeting",
        "/businesses/{business_id}/greeting",
    ]
    assert contribution.model_bases == ()


def test_greeting_requires_the_plugin_permission() -> None:
    without_grant = Role(
        slug=RoleSlug.BUSINESS_SERVICE_PROVIDER,
        name="Business / Service Provider",
        permissions=[],
    )
    response = TestClient(_app_with(User(roles=[without_grant]))).get("/greeting")
    assert response.status_code == 403
    assert response.json()["success"] is False


def test_greeting_returns_the_standard_envelope() -> None:
    role = Role(
        slug=RoleSlug.BUSINESS_SERVICE_PROVIDER,
        name="Business / Service Provider",
        permissions=[Permission(name=HelloPermission.GREETING_VIEW)],
    )
    response = TestClient(_app_with(User(roles=[role]))).get("/greeting")
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": HelloMessages.GREETING_RETRIEVED,
        "data": {"plugin": "hello", "greeting": HelloMessages.GREETING},
    }
