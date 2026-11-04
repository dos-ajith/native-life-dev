from collections.abc import Callable, Iterator
from pathlib import Path
from textwrap import dedent
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy import event

from app.api.deps import get_current_active_user, get_db
from app.core.database import engine
from app.core.permissions import RoleSlug
from app.models.plugin import Plugin, PluginStatus
from app.models.role import Role
from app.models.user import User
from app.repositories.plugin_repository import PluginRepository

REFERENCE_PLUGIN_ROOT = Path(__file__).resolve().parents[3] / "plugins" / "_reference" / "hello"
REFERENCE_VERSION = "1.1.0"

DEFAULT_ROUTES = """
from fastapi import APIRouter

from app.plugins.sdk import PluginContext, SuccessResponse

router = APIRouter()


@router.get("/ping", response_model=SuccessResponse[dict[str, str]])
def ping() -> SuccessResponse[dict[str, str]]:
    return SuccessResponse(message="pong", data={{"plugin": "{key}"}})


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""


def manifest_toml(
    key: str,
    *,
    version: str = "1.0.0",
    dependencies: str = "[]",
    core_api: str = ">=1.0,<2.0",
    role_scope: str = "business-service-provider",
    migrations: bool = False,
    extra: str = "",
) -> str:
    return dedent(
        f"""
        manifest_version = 1
        dependencies = {dependencies}
        categories = []

        [plugin]
        key = "{key}"
        name = "Test {key}"
        version = "{version}"
        role_scope = "{role_scope}"
        business_type = "product"

        [compatibility]
        core_api = "{core_api}"

        [api]
        prefix = "/plugins/{key}"
        tag = "1.5 Businesses · {key}"

        [database]
        table_prefix = "plg_{key}_"
        migrations = {str(migrations).lower()}

        [permissions."plugin.{key}.item.view"]
        description = "View {key} items"
        """
    ) + dedent(extra)


PluginWriter = Callable[..., Path]


def _refuse_connection(*_args: object) -> None:
    raise AssertionError("plugin unit tests must not connect to the database")


@pytest.fixture(autouse=True)
def forbid_database_connections() -> Iterator[None]:
    event.listen(engine, "connect", _refuse_connection)
    yield
    event.remove(engine, "connect", _refuse_connection)


@pytest.fixture
def write_plugin(tmp_path: Path) -> PluginWriter:
    def writer(
        key: str,
        *,
        directory: str | None = None,
        plugin_code: str | None = None,
        files: dict[str, str] | None = None,
        **manifest_options: Any,
    ) -> Path:
        root = tmp_path / "plugins" / (directory or key)
        root.mkdir(parents=True, exist_ok=True)
        (root / "__init__.py").write_text("")
        (root / "plugin.toml").write_text(manifest_toml(key, **manifest_options), encoding="utf-8")
        code = plugin_code if plugin_code is not None else DEFAULT_ROUTES.format(key=key)
        (root / "plugin.py").write_text(dedent(code))
        for name, content in (files or {}).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(dedent(content))
        return root

    return writer


@pytest.fixture
def plugins_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "plugins"
    directory.mkdir(exist_ok=True)
    return directory


def super_admin() -> User:
    return User(roles=[Role(slug=RoleSlug.SUPER_ADMIN, name="Super Admin", permissions=[])])


def individual_user() -> User:
    return User(roles=[Role(slug=RoleSlug.INDIVIDUAL_USER, name="Individual", permissions=[])])


def no_db() -> Iterator[None]:
    yield None


def override_auth(app: FastAPI, user: User) -> None:
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_db] = no_db


class PluginStatusTable:
    def __init__(self) -> None:
        self.rows: dict[str, Plugin] = {}

    def set(self, key: str, status: PluginStatus, version: str = "1.0.0") -> None:
        self.rows[key] = Plugin(key=key, status=status, version=version)


@pytest.fixture
def plugin_status(monkeypatch: pytest.MonkeyPatch) -> PluginStatusTable:
    table = PluginStatusTable()

    def get_by_key(_self: PluginRepository, key: str) -> Plugin | None:
        return table.rows.get(key)

    monkeypatch.setattr(PluginRepository, "get_by_key", get_by_key)
    return table
