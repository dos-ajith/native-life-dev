from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import AuthorizationError
from app.core.messages import BusinessMessages
from app.models.business import Business
from app.models.plugin import PluginStatus
from app.models.user import User
from app.plugins.mounting import mount_plugins
from app.plugins.registry import PluginLoadState
from app.services.business_plugin_service import BusinessPluginService
from tests.unit.plugins.conftest import (
    REFERENCE_PLUGIN_ROOT,
    REFERENCE_VERSION,
    PluginStatusTable,
    PluginWriter,
    individual_user,
    override_auth,
    super_admin,
)
from tests.unit.plugins.test_mounting import API, applied_registry, core_app

SCOPED_PLUGIN = """
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.plugins.sdk import PluginBusiness, PluginContext, SuccessResponse, require_business_plugin

router = APIRouter()


@router.get("/businesses/{{business_id}}/raw", response_model=SuccessResponse[dict[str, str]])
def raw(business_id: UUID) -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="raw", data={{"business_id": str(business_id)}})


@router.get("/businesses/{{business_id}}/declared", response_model=SuccessResponse[dict[str, str]])
def declared(
    business: Annotated[PluginBusiness, Depends(require_business_plugin("{access_key}"))],
) -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="declared", data={{"name": business.name}})


@router.get("/public", response_model=SuccessResponse[dict[str, str]])
def public() -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="public", data={{}})


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

UNSCOPED_DEPENDENCY_PLUGIN = """
from typing import Annotated

from fastapi import APIRouter, Depends

from app.plugins.sdk import PluginBusiness, PluginContext, SuccessResponse, require_business_plugin

router = APIRouter()


@router.get("/lookup", response_model=SuccessResponse[dict[str, str]])
def lookup(
    business: Annotated[PluginBusiness, Depends(require_business_plugin("shop"))],
) -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="lookup", data={"name": business.name})


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

WEBSOCKET_PLUGIN = """
from fastapi import APIRouter, WebSocket

from app.plugins.sdk import PluginContext

router = APIRouter()


@router.websocket("/businesses/{business_id}/live")
async def live(websocket: WebSocket) -> None:
    await websocket.close()


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""


class AccessRecorder:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str]] = []
        self.denied = False

    def __call__(self, business_id: UUID, plugin_key: str, actor: User) -> Business:
        self.calls.append((business_id, plugin_key))
        if self.denied:
            raise AuthorizationError(BusinessMessages.NOT_OWNER)
        return Business(id=business_id, owner_id=uuid4(), name="Corner Shop", category_id=None)


@pytest.fixture
def access(monkeypatch: pytest.MonkeyPatch) -> AccessRecorder:
    recorder = AccessRecorder()
    monkeypatch.setattr(BusinessPluginService, "authorize_access", recorder)
    return recorder


def _shop_client(
    write_plugin: PluginWriter, plugins_dir: Path, plugin_status: PluginStatusTable
) -> TestClient:
    write_plugin("shop", plugin_code=SCOPED_PLUGIN.format(access_key="shop"))
    plugin_status.set("shop", PluginStatus.ENABLED)
    application = core_app()
    mount_plugins(application, applied_registry(plugins_dir), API)
    override_auth(application, individual_user())
    return TestClient(application)


def _failure(write_plugin: PluginWriter, plugins_dir: Path, code: str) -> str:
    write_plugin("shop", plugin_code=code)
    registry = applied_registry(plugins_dir)
    outcome = registry.outcome_for("shop")
    assert outcome is not None and outcome.state == PluginLoadState.FAILED
    assert registry.plugins == ()
    return outcome.message or ""


def test_business_routes_are_checked_with_the_plugins_own_key_even_when_undeclared(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
) -> None:
    client = _shop_client(write_plugin, plugins_dir, plugin_status)
    business_id = uuid4()
    response = client.get(f"{API}/plugins/shop/businesses/{business_id}/raw")
    assert response.status_code == 200
    assert access.calls == [(business_id, "shop")]
    access.denied = True
    denied = client.get(f"{API}/plugins/shop/businesses/{business_id}/raw")
    assert denied.status_code == 403
    assert denied.json() == {"success": False, "message": BusinessMessages.NOT_OWNER, "errors": []}


def test_a_declared_check_runs_once_per_request(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
) -> None:
    client = _shop_client(write_plugin, plugins_dir, plugin_status)
    response = client.get(f"{API}/plugins/shop/businesses/{uuid4()}/declared")
    assert response.status_code == 200
    assert response.json()["data"] == {"name": "Corner Shop"}
    assert len(access.calls) == 1


def test_routes_without_a_business_are_not_business_checked(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
) -> None:
    client = _shop_client(write_plugin, plugins_dir, plugin_status)
    assert client.get(f"{API}/plugins/shop/public").status_code == 200
    assert access.calls == []


def test_globally_disabled_plugin_hides_business_routes_before_the_business_check(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
) -> None:
    client = _shop_client(write_plugin, plugins_dir, plugin_status)
    plugin_status.set("shop", PluginStatus.DISABLED)
    assert client.get(f"{API}/plugins/shop/businesses/{uuid4()}/raw").status_code == 404
    assert access.calls == []


def test_a_plugin_cannot_check_business_access_with_another_plugins_key(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    message = _failure(write_plugin, plugins_dir, SCOPED_PLUGIN.format(access_key="hello"))
    assert "'hello'" in message and "own key" in message


def test_the_business_dependency_requires_a_business_id_path_parameter(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    message = _failure(write_plugin, plugins_dir, UNSCOPED_DEPENDENCY_PLUGIN)
    assert "/lookup" in message and "no business_id path parameter" in message


def test_route_order_and_openapi_are_preserved(
    write_plugin: PluginWriter, plugins_dir: Path, plugin_status: PluginStatusTable
) -> None:
    client = _shop_client(write_plugin, plugins_dir, plugin_status)
    paths = [path for path in client.app.openapi()["paths"] if "/plugins/shop/" in path]  # type: ignore[attr-defined]
    assert paths == [
        f"{API}/plugins/shop/businesses/{{business_id}}/raw",
        f"{API}/plugins/shop/businesses/{{business_id}}/declared",
        f"{API}/plugins/shop/public",
    ]


def test_reference_business_greeting_checks_the_business_first(
    plugin_status: PluginStatusTable, access: AccessRecorder
) -> None:
    plugin_status.set("hello", PluginStatus.ENABLED, version=REFERENCE_VERSION)
    application = core_app()
    mount_plugins(application, applied_registry(REFERENCE_PLUGIN_ROOT.parent), API)
    override_auth(application, super_admin())
    client = TestClient(application)
    business_id = uuid4()
    path = f"{API}/plugins/hello/businesses/{business_id}/greeting"
    response = client.get(path)
    assert response.status_code == 200
    assert response.json()["data"]["business_name"] == "Corner Shop"
    assert access.calls == [(business_id, "hello")]
    access.denied = True
    override_auth(application, individual_user())
    denied = client.get(path)
    assert denied.status_code == 403
    assert denied.json()["message"] == BusinessMessages.NOT_OWNER


TYPED_CONVERTER_PLUGIN = """
from uuid import UUID

from fastapi import APIRouter

from app.plugins.sdk import PluginContext, SuccessResponse

router = APIRouter()


@router.get("/businesses/{business_id:uuid}/typed", response_model=SuccessResponse[dict[str, str]])
def typed(business_id: UUID) -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="typed", data={"business_id": str(business_id)})


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

BUSINESS_ID_PARAMETER_PLUGIN = """
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header

from app.plugins.sdk import PluginContext

router = APIRouter()


def business_from_query(business_id: UUID) -> UUID:
    return business_id


@router.get("/orders")
def orders({parameter}) -> dict[str, str]:
    return {{}}


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

STARLETTE_ROUTE_PLUGIN = """
from fastapi import APIRouter
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.plugins.sdk import PluginContext


async def raw(request: Request) -> JSONResponse:
    return JSONResponse({"business": request.path_params["biz"]})


router = APIRouter()
router.add_route("/businesses/{biz}/raw", raw, methods=["GET"])


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

MOUNT_PLUGIN = """
from fastapi import APIRouter, FastAPI

from app.plugins.sdk import PluginContext

sub = FastAPI()


@sub.get("/hi")
def hi() -> dict[str, str]:
    return {"hi": "there"}


router = APIRouter()
router.mount("/sub", sub)


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

NESTED_ROUTER_PLUGIN = """
from fastapi import APIRouter

from app.plugins.sdk import PluginContext

child = APIRouter()


@child.get("/items")
def items() -> dict[str, str]:
    return {}


router = APIRouter()
router.include_router(child, prefix="/child")


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

CUSTOM_ROUTE_CLASS_PLUGIN = """
from fastapi import APIRouter
from fastapi.routing import APIRoute

from app.plugins.sdk import PluginContext


class QuietRoute(APIRoute):
    pass


router = APIRouter(route_class=QuietRoute)


@router.get("/quiet")
def quiet() -> dict[str, str]:
    return {}


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""

ROUTE_COUNT = 1000


def _many_routes_plugin(alternate: bool) -> str:
    routes = []
    for index in range(ROUTE_COUNT):
        path = f"/businesses/{{business_id}}/r{index}" if alternate and index % 2 else f"/r{index}"
        routes.append(
            f'@router.get("{path}")\ndef route_{index}() -> dict[str, int]:\n'
            f'    return {{"index": {index}}}\n'
        )
    return (
        "from fastapi import APIRouter\n\nfrom app.plugins.sdk import PluginContext\n\n"
        "router = APIRouter()\n\n"
        + "\n".join(routes)
        + "\n\ndef register(ctx: PluginContext) -> None:\n    ctx.include_router(router)\n"
    )


def test_typed_converter_routes_are_business_checked(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
) -> None:
    write_plugin("shop", plugin_code=TYPED_CONVERTER_PLUGIN)
    plugin_status.set("shop", PluginStatus.ENABLED)
    application = core_app()
    mount_plugins(application, applied_registry(plugins_dir), API)
    override_auth(application, individual_user())
    client = TestClient(application)
    business_id = uuid4()
    path = f"{API}/plugins/shop/businesses/{business_id}/typed"
    assert client.get(path).status_code == 200
    assert access.calls == [(business_id, "shop")]
    access.denied = True
    assert client.get(path).status_code == 403


@pytest.mark.parametrize(
    ("parameter", "location"),
    [
        ("business_id: UUID", "query"),
        ('owner: Annotated[str, Header(alias="business_id")]', "header"),
        ("business: Annotated[UUID, Depends(business_from_query)]", "query"),
    ],
)
def test_business_id_outside_the_path_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path, parameter: str, location: str
) -> None:
    code = BUSINESS_ID_PARAMETER_PLUGIN.format(parameter=parameter)
    message = _failure(write_plugin, plugins_dir, code)
    assert f"business_id as a {location} parameter" in message


@pytest.mark.parametrize(
    ("code", "path", "kind"),
    [
        (STARLETTE_ROUTE_PLUGIN, "/plugins/shop/businesses/{business_id}/raw", "Route"),
        (MOUNT_PLUGIN, "/plugins/shop/sub/hi", "Mount"),
        (WEBSOCKET_PLUGIN, None, "APIWebSocketRoute"),
        (NESTED_ROUTER_PLUGIN, "/plugins/shop/child/items", "_IncludedRouter"),
        (CUSTOM_ROUTE_CLASS_PLUGIN, "/plugins/shop/quiet", "QuietRoute"),
    ],
)
def test_unsupported_route_types_are_rejected_and_never_served(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
    code: str,
    path: str | None,
    kind: str,
) -> None:
    message = _failure(write_plugin, plugins_dir, code)
    assert f"is a {kind};" in message
    if path is None:
        return
    application = core_app()
    mount_plugins(application, applied_registry(plugins_dir), API)
    override_auth(application, individual_user())
    client = TestClient(application)
    url = f"{API}{path}".replace("{business_id}", str(uuid4()))
    for status in (PluginStatus.DISABLED, PluginStatus.ENABLED):
        plugin_status.set("shop", status)
        assert client.get(url).status_code == 404
    assert access.calls == []


@pytest.mark.parametrize("alternate", [False, True])
def test_a_thousand_plugin_routes_start_up_and_keep_their_order(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    access: AccessRecorder,
    alternate: bool,
) -> None:
    write_plugin("shop", plugin_code=_many_routes_plugin(alternate))
    plugin_status.set("shop", PluginStatus.ENABLED)
    application = core_app()
    lifespan = application.router.lifespan_context
    core_routes = len(application.router.routes)
    mount_plugins(application, applied_registry(plugins_dir), API)
    assert application.router.lifespan_context is lifespan
    groups = len(application.router.routes) - core_routes
    assert groups == (ROUTE_COUNT if alternate else 1)
    override_auth(application, individual_user())
    with TestClient(application) as client:
        assert client.get(f"{API}/plugins/shop/r0").json() == {"index": 0}
        last = ROUTE_COUNT - 1
        last_path = f"businesses/{uuid4()}/r{last}" if alternate else f"r{last}"
        assert client.get(f"{API}/plugins/shop/{last_path}").json() == {"index": last}
    paths = [path for path in application.openapi()["paths"] if "/plugins/shop/" in path]
    assert len(paths) == ROUTE_COUNT
    assert paths[0].endswith("/r0") and paths[-1].endswith(f"/r{ROUTE_COUNT - 1}")
    assert len(access.calls) == (1 if alternate else 0)
