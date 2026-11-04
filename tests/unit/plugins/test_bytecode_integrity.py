import importlib.util
import os
import py_compile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.models.plugin import PluginStatus
from app.plugins.mounting import mount_plugins
from app.plugins.registry import PluginLoadState, PluginRegistry
from tests.unit.plugins.conftest import (
    PluginStatusTable,
    PluginWriter,
    override_auth,
    super_admin,
)
from tests.unit.plugins.test_mounting import API, applied_registry, core_app

REAL = "VALUE = 'source'\n"
FORGED = "VALUE = 'forged'\n"

VALUE_PLUGIN = """
from fastapi import APIRouter

from app.plugins.sdk import PluginContext

from {import_from} import VALUE

router = APIRouter()


@router.get("/value")
def value() -> dict[str, str]:
    return {{"value": VALUE}}


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""


def _forge_timestamp_cache(source: Path) -> None:
    source.write_text(FORGED)
    py_compile.compile(str(source), invalidation_mode=py_compile.PycInvalidationMode.TIMESTAMP)
    stat = source.stat()
    source.write_text(REAL)
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))


def _forge_unchecked_cache(source: Path, scratch: Path) -> None:
    forged = scratch / f"forged_{uuid4().hex}.py"
    forged.write_text(FORGED)
    source.write_text(REAL)
    py_compile.compile(
        str(forged),
        cfile=importlib.util.cache_from_source(str(source)),
        invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
    )


def _standard_import_value(source: Path) -> str:
    spec = importlib.util.spec_from_file_location(f"control_{uuid4().hex}", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value: str = module.VALUE
    return value


def _served_value(registry: PluginRegistry, plugin_status: PluginStatusTable) -> str:
    plugin_status.set("shop", PluginStatus.ENABLED)
    application = core_app()
    mount_plugins(application, registry, API)
    override_auth(application, super_admin())
    response = TestClient(application).get(f"{API}/plugins/shop/value")
    assert response.status_code == 200
    value: str = response.json()["value"]
    return value


@pytest.mark.parametrize("forgery", ["timestamp", "unchecked_hash"])
@pytest.mark.parametrize(
    ("module_file", "import_from", "extra_files"),
    [
        ("values.py", ".values", {}),
        ("__init__.py", ".", {}),
        ("lib/helpers.py", ".lib.helpers", {}),
        ("backend/values.py", ".backend.values", {"backend/__init__.py": ""}),
    ],
)
def test_forged_cached_bytecode_is_never_executed(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    tmp_path: Path,
    forgery: str,
    module_file: str,
    import_from: str,
    extra_files: dict[str, str],
) -> None:
    root = write_plugin(
        "shop", plugin_code=VALUE_PLUGIN.format(import_from=import_from), files=extra_files
    )
    source = root / module_file
    source.parent.mkdir(parents=True, exist_ok=True)
    if forgery == "timestamp":
        _forge_timestamp_cache(source)
    else:
        _forge_unchecked_cache(source, tmp_path)
    assert _standard_import_value(source) == "forged"
    registry = applied_registry(plugins_dir)
    assert registry.outcome_for("shop").state == PluginLoadState.LOADED  # type: ignore[union-attr]
    assert _served_value(registry, plugin_status) == "source"


def test_cache_entry_without_a_source_file_cannot_be_imported(
    write_plugin: PluginWriter, plugins_dir: Path, tmp_path: Path
) -> None:
    root = write_plugin("shop", plugin_code=VALUE_PLUGIN.format(import_from=".ghost"))
    ghost_source = tmp_path / "ghost.py"
    ghost_source.write_text(FORGED)
    py_compile.compile(
        str(ghost_source), cfile=importlib.util.cache_from_source(str(root / "ghost.py"))
    )
    assert not (root / "ghost.py").exists()
    registry = applied_registry(plugins_dir)
    outcome = registry.outcome_for("shop")
    assert outcome is not None and outcome.state == PluginLoadState.FAILED
    assert "ModuleNotFoundError" in (outcome.message or "")
    assert registry.plugins == ()


def test_loading_a_plugin_writes_no_bytecode_into_its_directory(
    write_plugin: PluginWriter,
    plugins_dir: Path,
    plugin_status: PluginStatusTable,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("sys.dont_write_bytecode", False)
    root = write_plugin(
        "shop",
        plugin_code=VALUE_PLUGIN.format(import_from=".backend.values"),
        files={"backend/__init__.py": "", "backend/values.py": REAL},
    )
    assert _served_value(applied_registry(plugins_dir), plugin_status) == "source"
    assert list(root.rglob("__pycache__")) == []
