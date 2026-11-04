from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.plugin import PluginStatus
from app.plugins.discovery import discover_plugins, plugin_content_sha256
from app.plugins.errors import PluginError
from app.plugins.manifest import parse_manifest
from app.plugins.mounting import mount_plugins
from app.plugins.registry import PluginLoadState
from tests.unit.plugins.conftest import (
    PluginStatusTable,
    PluginWriter,
    manifest_toml,
    override_auth,
    super_admin,
)
from tests.unit.plugins.test_mounting import API, applied_registry, core_app

BACKEND_ENTRYPOINT = """
[entrypoint]
module = "backend.plugin"
"""

BACKEND_FILES = {
    "backend/__init__.py": "",
    "backend/plugin.py": """
        from app.plugins.sdk import PluginContext

        from .routes.catalog import router


        def register(ctx: PluginContext) -> None:
            ctx.include_router(router)
        """,
    "backend/routes/__init__.py": "",
    "backend/routes/catalog.py": """
        from fastapi import APIRouter

        from app.plugins.sdk import SuccessResponse

        from ..services.catalog_service import featured_items

        router = APIRouter()


        @router.get("/items", response_model=SuccessResponse[list[str]])
        def list_items() -> SuccessResponse[list[str]]:
            return SuccessResponse(message="items", data=featured_items())
        """,
    "backend/services/__init__.py": "",
    "backend/services/catalog_service.py": """
        def featured_items() -> list[str]:
            return ["tea", "coffee"]
        """,
}

FRONTEND_SECTIONS = """
[frontend]
path = "{frontend_path}"
entry = "{frontend_entry}"

[admin_panel]
path = "admin_panel"
entry = "dist/index.js"
"""

UI_FILES = {"frontend/dist/index.js": "export {}\n", "admin_panel/dist/index.js": "export {}\n"}


def _ui_extra(frontend_path: str = "frontend", frontend_entry: str = "dist/index.js") -> str:
    return FRONTEND_SECTIONS.format(frontend_path=frontend_path, frontend_entry=frontend_entry)


def test_nested_module_with_a_backend_package_loads_and_serves(
    write_plugin: PluginWriter, plugins_dir: Path, plugin_status: PluginStatusTable
) -> None:
    write_plugin("shop", directory="product/shop", extra=BACKEND_ENTRYPOINT, files=BACKEND_FILES)
    registry = applied_registry(plugins_dir)
    assert registry.outcome_for("shop").state == PluginLoadState.LOADED  # type: ignore[union-attr]
    plugin_status.set("shop", PluginStatus.ENABLED)
    application = core_app()
    mount_plugins(application, registry, API)
    override_auth(application, super_admin())
    response = TestClient(application).get(f"{API}/plugins/shop/items")
    assert response.status_code == 200
    assert response.json()["data"] == ["tea", "coffee"]


def test_plugin_directories_inside_another_plugin_are_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    outer = write_plugin("shop", directory="product/shop")
    nested = write_plugin("inner", directory="product/shop/backend/inner")
    result = discover_plugins(plugins_dir)
    assert [candidate.key for candidate in result.candidates] == ["shop"]
    assert [failure.root for failure in result.failures] == [nested]
    assert str(outer) in result.failures[0].error


def test_manifests_inside_build_tool_directories_are_ignored(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("shop", directory="product/shop")
    write_plugin("vendored", directory="product/shop/frontend/node_modules/vendored")
    result = discover_plugins(plugins_dir)
    assert [candidate.key for candidate in result.candidates] == ["shop"]
    assert result.failures == ()


def test_content_hash_ignores_build_tool_directories_and_generated_files(
    write_plugin: PluginWriter,
) -> None:
    root = write_plugin("shop", files=UI_FILES, extra=_ui_extra())
    original = plugin_content_sha256(root)
    for generated in (
        "frontend/node_modules/react/index.js",
        ".git/HEAD",
        ".venv/lib/site.py",
        "frontend/.next/cache.json",
        "frontend/.DS_Store",
        "backend/__pycache__/plugin.cpython-312.pyc",
    ):
        path = root / generated
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("generated\n")
    assert plugin_content_sha256(root) == original
    (root / "frontend" / "dist" / "index.js").write_text("export const changed = true\n")
    assert plugin_content_sha256(root) != original


def test_frontend_and_admin_panel_metadata_is_validated(write_plugin: PluginWriter) -> None:
    root = write_plugin("shop", files=UI_FILES, extra=_ui_extra())
    candidate = discover_plugins(root.parent).candidates[0]
    assert candidate.manifest.frontend is not None
    assert candidate.manifest.frontend.entry == "dist/index.js"
    assert set(candidate.manifest.ui_bundles) == {"frontend", "admin_panel"}


def test_manifest_without_ui_sections_stays_valid() -> None:
    manifest = parse_manifest(manifest_toml("shop").encode())
    assert manifest.frontend is None and manifest.admin_panel is None
    assert manifest.ui_bundles == {}


@pytest.mark.parametrize(
    ("frontend_path", "frontend_entry"),
    [
        ("/etc", "passwd"),
        ("../outside", "index.js"),
        ("frontend", "../../plugin.py"),
        (".hidden", "index.js"),
        ("frontend/node_modules", "index.js"),
        ("frontend", "tests/index.js"),
        ("frontend//dist", "index.js"),
        ("C:/frontend", "index.js"),
    ],
)
def test_unsafe_ui_paths_are_rejected(frontend_path: str, frontend_entry: str) -> None:
    manifest = manifest_toml("shop", extra=_ui_extra(frontend_path, frontend_entry))
    with pytest.raises(PluginError, match="relative path"):
        parse_manifest(manifest.encode())


def test_missing_ui_entry_fails_discovery(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("shop", files=UI_FILES, extra=_ui_extra(frontend_entry="dist/missing.js"))
    result = discover_plugins(plugins_dir)
    assert result.candidates == ()
    assert "frontend entry 'frontend/dist/missing.js'" in result.failures[0].error


def test_ui_entry_symlinked_outside_the_plugin_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.js"
    outside.write_text("export {}\n")
    root = write_plugin("shop", files=UI_FILES, extra=_ui_extra(frontend_entry="dist/linked.js"))
    (root / "frontend" / "dist" / "linked.js").symlink_to(outside)
    result = discover_plugins(plugins_dir)
    assert result.candidates == ()
    assert "frontend/dist/linked.js' is a symlink" in result.failures[0].error


OUTSIDE_IMPORT_PLUGIN = """
from fastapi import APIRouter

from app.plugins.sdk import PluginContext

from .linked.evil import VALUE

router = APIRouter()


@router.get("/value")
def value() -> dict[str, str]:
    return {"value": VALUE}


def register(ctx: PluginContext) -> None:
    ctx.include_router(router)
"""


def _outside_package(tmp_path: Path) -> Path:
    outside = tmp_path / "outside_pkg"
    outside.mkdir()
    (outside / "__init__.py").write_text("")
    (outside / "evil.py").write_text("import app.core.config\nVALUE = 'unhashed'\n")
    return outside


def test_symlinked_directory_to_outside_code_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path, tmp_path: Path
) -> None:
    root = write_plugin("shop", plugin_code=OUTSIDE_IMPORT_PLUGIN)
    (root / "linked").symlink_to(_outside_package(tmp_path), target_is_directory=True)
    result = discover_plugins(plugins_dir)
    assert result.candidates == ()
    assert (
        result.failures[0].error
        == "'linked' is a symlink; plugin directories must not contain symlinks"
    )
    registry = applied_registry(plugins_dir)
    assert registry.plugins == ()


def test_symlinked_files_and_nested_symlinks_are_rejected(
    write_plugin: PluginWriter, plugins_dir: Path, tmp_path: Path
) -> None:
    outside = _outside_package(tmp_path)
    root = write_plugin("shop", files=BACKEND_FILES)
    (root / "backend" / "services" / "evil.py").symlink_to(outside / "evil.py")
    result = discover_plugins(plugins_dir)
    assert "backend/services/evil.py' is a symlink" in result.failures[0].error


def test_symlinked_build_tool_directory_is_rejected_but_links_inside_it_are_ignored(
    write_plugin: PluginWriter, plugins_dir: Path, tmp_path: Path
) -> None:
    root = write_plugin("shop")
    modules = root / "frontend" / "node_modules"
    (modules / ".bin").mkdir(parents=True)
    (modules / ".bin" / "vite").symlink_to(tmp_path)
    assert [candidate.key for candidate in discover_plugins(plugins_dir).candidates] == ["shop"]
    (root / "frontend" / "node_modules" / ".bin" / "vite").unlink()
    (modules / ".bin").rmdir()
    modules.rmdir()
    modules.symlink_to(tmp_path, target_is_directory=True)
    assert "frontend/node_modules' is a symlink" in discover_plugins(plugins_dir).failures[0].error


@pytest.mark.parametrize("location", ["compiled.pyc", "backend/legacy.pyo"])
def test_stray_compiled_python_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path, location: str
) -> None:
    root = write_plugin("shop", files=BACKEND_FILES)
    (root / location).write_bytes(b"\x00compiled")
    result = discover_plugins(plugins_dir)
    assert result.candidates == ()
    assert f"'{location}' is compiled Python outside __pycache__" in result.failures[0].error


def test_bytecode_cache_directories_are_still_allowed(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    root = write_plugin("shop", files=BACKEND_FILES)
    cache = root / "backend" / "__pycache__"
    cache.mkdir()
    (cache / "plugin.cpython-312.pyc").write_bytes(b"cache")
    assert [candidate.key for candidate in discover_plugins(plugins_dir).candidates] == ["shop"]
