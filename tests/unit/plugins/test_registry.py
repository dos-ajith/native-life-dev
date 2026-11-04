from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import joinedload

import app.models  # noqa: F401
from app.models.base import Base as CoreBase
from app.models.business import Business
from app.plugins.discovery import discover_plugins
from app.plugins.errors import PluginError
from app.plugins.metadata import ensure_isolated_base
from app.plugins.registry import AppliedPlugin, PluginLoadState, PluginRegistry, build_registry
from app.plugins.versioning import CORE_API_VERSION
from tests.unit.plugins.conftest import PluginWriter

ISOLATED_MODELS = """
from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.plugins.sdk import UUIDPrimaryKeyMixin


class Base(DeclarativeBase):
    metadata = MetaData()


class Item(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "{table}"
    name: Mapped[str] = mapped_column(String(50))
{extra}
"""

MODEL_PLUGIN = """
from app.plugins.sdk import PluginContext

from .models import Base


def register(ctx: PluginContext) -> None:
    ctx.register_models(Base)
"""


def _applied(plugins_dir: Path) -> dict[str, AppliedPlugin]:
    return {
        candidate.key: AppliedPlugin(
            version=str(candidate.manifest.version), content_sha256=candidate.content_sha256
        )
        for candidate in discover_plugins(plugins_dir).candidates
    }


def _build(plugins_dir: Path, applied: dict[str, AppliedPlugin] | None = None) -> PluginRegistry:
    snapshot = _applied(plugins_dir) if applied is None else applied
    return build_registry(plugins_dir, snapshot, CORE_API_VERSION)


def _states(registry: PluginRegistry) -> dict[str | None, PluginLoadState]:
    return {outcome.key: outcome.state for outcome in registry.outcomes}


def _message(registry: PluginRegistry, key: str) -> str:
    outcome = registry.outcome_for(key)
    assert outcome is not None
    return outcome.message or ""


def _core_query_compiles() -> bool:
    statement = select(Business).options(joinedload(Business.category))
    return bool(statement.compile(dialect=postgresql.dialect()))


def test_empty_directory_builds_an_empty_registry(plugins_dir: Path) -> None:
    registry = _build(plugins_dir, {})
    assert registry.plugins == ()
    assert registry.outcomes == ()
    assert registry.openapi_tags == ()


def test_applied_plugin_is_loaded_with_its_router(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog")
    registry = _build(plugins_dir)
    loaded = registry.get("catalog")
    assert loaded is not None
    assert [route.path for route in loaded.routers[0].routes] == ["/ping"]
    assert registry.openapi_tags == ("1.5 Businesses · catalog",)
    assert _states(registry) == {"catalog": PluginLoadState.LOADED}


def test_plugins_on_disk_are_not_loaded_until_applied(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog")
    registry = _build(plugins_dir, {})
    assert registry.plugins == ()
    outcome = registry.outcome_for("catalog")
    assert outcome is not None and outcome.state == PluginLoadState.SKIPPED
    assert outcome.message is not None and "not applied" in outcome.message


def test_version_or_content_drift_since_apply_is_not_loaded(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    root = write_plugin("catalog")
    applied = _applied(plugins_dir)
    (root / "plugin.py").write_text((root / "plugin.py").read_text() + "\n# edited\n")
    changed = _build(plugins_dir, applied)
    assert changed.plugins == ()
    assert "changed since" in _message(changed, "catalog")
    other_version = {"catalog": AppliedPlugin(version="0.9.0", content_sha256="x")}
    assert "differs from applied" in _message(_build(plugins_dir, other_version), "catalog")


def test_failing_plugin_is_skipped_and_others_still_load(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("good")
    write_plugin(
        "broken",
        plugin_code="""
        def register(ctx):
            raise RuntimeError("secret-token-value")
        """,
    )
    write_plugin("dependent", dependencies='[{ key = "broken", version = ">=1.0" }]')
    registry = _build(plugins_dir)
    assert [plugin.key for plugin in registry.plugins] == ["good"]
    states = _states(registry)
    assert states["broken"] == PluginLoadState.FAILED
    assert states["dependent"] == PluginLoadState.FAILED
    broken_message = _message(registry, "broken")
    assert "RuntimeError" in broken_message
    assert "secret-token-value" not in broken_message


def test_import_errors_and_missing_entrypoints_fail_cleanly(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("noimport", plugin_code="from json import does_not_exist_anywhere\n")
    write_plugin("noentry", plugin_code="value = 1\n")
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "Importing the plugin failed" in _message(registry, "noimport")
    assert "not found or is not callable" in _message(registry, "noentry")


def test_boundary_violations_prevent_loading(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin(
        "sneaky",
        plugin_code="""
        from app.core.config import get_settings

        def register(ctx):
            pass
        """,
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "app.core.config" in _message(registry, "sneaky")


def test_routes_with_their_own_tags_are_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin(
        "tagged",
        plugin_code="""
        from fastapi import APIRouter

        router = APIRouter(tags=["admin"])

        @router.get("/x")
        def x() -> None:
            return None

        def register(ctx):
            ctx.include_router(router)
        """,
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "own OpenAPI tags" in _message(registry, "tagged")


def test_isolated_plugin_models_load(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin(
        "modelok",
        plugin_code=MODEL_PLUGIN,
        files={"models.py": ISOLATED_MODELS.format(table="plg_modelok_items", extra="")},
    )
    registry = _build(plugins_dir)
    loaded = registry.get("modelok")
    assert loaded is not None
    base = loaded.model_bases[0]
    assert "plg_modelok_items" in base.metadata.tables
    assert "plg_modelok_items" not in CoreBase.metadata.tables


def test_table_prefix_is_enforced(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin(
        "badtable",
        plugin_code=MODEL_PLUGIN,
        files={"models.py": ISOLATED_MODELS.format(table="items", extra="")},
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "must start with 'plg_badtable_'" in _message(registry, "badtable")


def test_broken_plugin_mapper_does_not_break_core_queries(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    broken_relationship = (
        '    missing: Mapped["NoSuchClass"] = relationship("NoSuchClass")  # noqa: F821'
    )
    write_plugin(
        "brokenmodel",
        plugin_code=MODEL_PLUGIN,
        files={
            "models.py": ISOLATED_MODELS.format(
                table="plg_brokenmodel_items", extra=broken_relationship
            )
        },
    )
    assert _core_query_compiles()
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "Model configuration failed" in _message(registry, "brokenmodel")
    assert _core_query_compiles()


def test_core_declarative_base_is_never_accepted_as_a_plugin_base() -> None:
    try:
        ensure_isolated_base(CoreBase, "plg_x_")
    except PluginError as exc:
        assert "separate MetaData" in exc.message
    else:
        raise AssertionError("core base was accepted")


def test_router_lifecycle_hooks_are_rejected(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin(
        "hooks",
        plugin_code="""
        from fastapi import APIRouter

        def started() -> None:
            pass

        router = APIRouter(on_startup=[started])

        def register(ctx):
            ctx.include_router(router)
        """,
    )
    write_plugin(
        "lifespan",
        plugin_code="""
        from contextlib import asynccontextmanager
        from fastapi import APIRouter

        @asynccontextmanager
        async def lifespan(app):
            yield

        router = APIRouter(lifespan=lifespan)

        def register(ctx):
            ctx.include_router(router)
        """,
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    for key in ("hooks", "lifespan"):
        assert "on_startup, on_shutdown or lifespan" in _message(registry, key)


def test_route_that_breaks_openapi_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin(
        "badschema",
        plugin_code="""
        from typing import Any
        from fastapi import APIRouter
        from pydantic import BaseModel
        from pydantic_core import core_schema

        class Opaque:
            @classmethod
            def __get_pydantic_core_schema__(cls, source: Any, handler: Any) -> Any:
                return core_schema.any_schema()

            @classmethod
            def __get_pydantic_json_schema__(cls, schema: Any, handler: Any) -> Any:
                raise ValueError("no schema")

        class Body(BaseModel):
            value: Opaque

        router = APIRouter()

        @router.post("/x")
        def x(body: Body) -> None:
            return None

        def register(ctx):
            ctx.include_router(router)
        """,
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "OpenAPI schema failed: ValueError" in _message(registry, "badschema")


def test_unregistered_model_bases_are_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin(
        "hidden",
        plugin_code="""
        from .models import Item

        def register(ctx):
            pass
        """,
        files={"models.py": ISOLATED_MODELS.format(table="hidden_items", extra="")},
    )
    registry = _build(plugins_dir)
    assert registry.plugins == ()
    assert "not passed to ctx.register_models" in _message(registry, "hidden")


def test_system_exit_during_import_is_contained(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("exits", plugin_code="raise SystemExit(3)\n")
    write_plugin("good")
    registry = _build(plugins_dir)
    assert [plugin.key for plugin in registry.plugins] == ["good"]
    assert "SystemExit" in _message(registry, "exits")


def test_failed_optional_dependency_does_not_take_down_dependents(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("extras", plugin_code="raise RuntimeError('boom')\n")
    write_plugin("catalog", dependencies='[{ key = "extras", version = ">=1.0", optional = true }]')
    registry = _build(plugins_dir)
    assert [plugin.key for plugin in registry.plugins] == ["catalog"]
    assert _states(registry)["extras"] == PluginLoadState.FAILED
