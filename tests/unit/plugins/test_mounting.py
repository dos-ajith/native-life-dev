from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.deps import get_db
from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.messages import PluginMessages
from app.core.openapi_tags import OPENAPI_TAGS
from app.main import app_error_handler, http_error_handler
from app.models.plugin import PluginStatus
from app.plugins.discovery import discover_plugins
from app.plugins.mounting import mount_plugins
from app.plugins.registry import AppliedPlugin, PluginRegistry, build_registry
from app.plugins.versioning import CORE_API_VERSION
from tests.unit.plugins.conftest import (
    REFERENCE_PLUGIN_ROOT,
    REFERENCE_VERSION,
    PluginStatusTable,
    PluginWriter,
    individual_user,
    no_db,
    override_auth,
    super_admin,
)

API = get_settings().api_v1_prefix
GREETING_PATH = f"{API}/plugins/hello/greeting"


def core_app() -> FastAPI:
    application = FastAPI(openapi_tags=OPENAPI_TAGS)
    application.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    application.add_exception_handler(StarletteHTTPException, http_error_handler)  # type: ignore[arg-type]
    application.include_router(api_router, prefix=API)
    application.dependency_overrides[get_db] = no_db
    return application


def applied_registry(plugins_dir: Path) -> PluginRegistry:
    applied = {
        candidate.key: AppliedPlugin(
            version=str(candidate.manifest.version), content_sha256=candidate.content_sha256
        )
        for candidate in discover_plugins(plugins_dir).candidates
    }
    return build_registry(plugins_dir, applied, CORE_API_VERSION)


def reference_app() -> FastAPI:
    application = core_app()
    mount_plugins(application, applied_registry(REFERENCE_PLUGIN_ROOT.parent), API)
    return application


def _tags(application: FastAPI) -> tuple[set[str], set[str]]:
    schema = application.openapi()
    declared = {tag["name"] for tag in application.openapi_tags or []}
    used = {
        tag
        for operations in schema["paths"].values()
        for operation in operations.values()
        for tag in operation.get("tags", [])
    }
    return declared, used


def test_zero_plugins_leave_the_core_api_unchanged(plugins_dir: Path) -> None:
    untouched = core_app()
    with_framework = core_app()
    mount_plugins(with_framework, applied_registry(plugins_dir), API)
    assert with_framework.openapi()["paths"] == untouched.openapi()["paths"]
    assert with_framework.openapi_tags == OPENAPI_TAGS
    declared, used = _tags(with_framework)
    assert used == declared


def test_reference_plugin_route_and_tag_are_registered() -> None:
    application = reference_app()
    assert GREETING_PATH in application.openapi()["paths"]
    declared, used = _tags(application)
    assert "1.5 Businesses · Hello" in used
    assert used == declared


def test_reference_endpoint_returns_the_standard_envelope(
    plugin_status: PluginStatusTable,
) -> None:
    plugin_status.set("hello", PluginStatus.ENABLED, REFERENCE_VERSION)
    application = reference_app()
    override_auth(application, super_admin())
    response = TestClient(application).get(GREETING_PATH)
    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "message": "Greeting retrieved",
        "data": {"plugin": "hello", "greeting": "Hello from the Native Life plugin framework"},
    }


def test_disable_and_reenable_take_effect_without_restart(
    plugin_status: PluginStatusTable,
) -> None:
    application = reference_app()
    override_auth(application, super_admin())
    client = TestClient(application)
    plugin_status.set("hello", PluginStatus.ENABLED, REFERENCE_VERSION)
    assert client.get(GREETING_PATH).status_code == 200
    plugin_status.set("hello", PluginStatus.DISABLED, REFERENCE_VERSION)
    disabled = client.get(GREETING_PATH)
    assert disabled.status_code == 404
    assert disabled.json() == {
        "success": False,
        "message": PluginMessages.NOT_AVAILABLE,
        "errors": [],
    }
    plugin_status.set("hello", PluginStatus.ENABLED, REFERENCE_VERSION)
    assert client.get(GREETING_PATH).status_code == 200


def test_installed_but_never_enabled_and_unregistered_plugins_do_not_serve(
    plugin_status: PluginStatusTable,
) -> None:
    application = reference_app()
    override_auth(application, super_admin())
    client = TestClient(application)
    assert client.get(GREETING_PATH).status_code == 404
    plugin_status.set("hello", PluginStatus.INSTALLED, REFERENCE_VERSION)
    assert client.get(GREETING_PATH).status_code == 404


def test_upgraded_but_not_restarted_plugin_refuses_to_serve(
    plugin_status: PluginStatusTable,
) -> None:
    plugin_status.set("hello", PluginStatus.ENABLED, version="1.2.0")
    application = reference_app()
    override_auth(application, super_admin())
    response = TestClient(application).get(GREETING_PATH)
    assert response.status_code == 503
    assert response.json()["message"] == PluginMessages.RESTART_REQUIRED


def test_plugin_endpoint_still_enforces_authentication_and_permissions(
    plugin_status: PluginStatusTable,
) -> None:
    plugin_status.set("hello", PluginStatus.ENABLED, REFERENCE_VERSION)
    application = reference_app()
    client = TestClient(application)
    assert client.get(GREETING_PATH).status_code == 401
    override_auth(application, individual_user())
    assert client.get(GREETING_PATH).status_code == 403


def test_disabled_plugin_hides_itself_before_authentication(
    plugin_status: PluginStatusTable,
) -> None:
    plugin_status.set("hello", PluginStatus.DISABLED, REFERENCE_VERSION)
    assert TestClient(reference_app()).get(GREETING_PATH).status_code == 404


def test_failing_plugin_does_not_break_core_or_other_plugins(
    write_plugin: PluginWriter, plugins_dir: Path, plugin_status: PluginStatusTable
) -> None:
    write_plugin("good")
    write_plugin("broken", plugin_code="raise RuntimeError('boom at import')\n")
    registry = applied_registry(plugins_dir)
    application = core_app()
    mount_plugins(application, registry, API)
    plugin_status.set("good", PluginStatus.ENABLED)
    client = TestClient(application)
    assert client.get(f"{API}/health").status_code == 200
    assert client.get(f"{API}/plugins/good/ping").status_code == 200
    assert client.get(f"{API}/plugins/broken/ping").status_code == 404
    declared, used = _tags(application)
    assert used == declared
    assert "1.5 Businesses · broken" not in declared
