from pathlib import Path

from app.plugins.discovery import discover_plugins
from app.plugins.resolution import Resolution, resolve_load_order
from app.plugins.versioning import CORE_API_VERSION
from tests.unit.plugins.conftest import PluginWriter


def _resolve(plugins_dir: Path) -> Resolution:
    return resolve_load_order(discover_plugins(plugins_dir).candidates, CORE_API_VERSION)


def _dependency(key: str, version: str = ">=1.0,<2.0", optional: bool = False) -> str:
    return f'[{{ key = "{key}", version = "{version}", optional = {str(optional).lower()} }}]'


def test_dependencies_load_before_dependents(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("ecommerce", dependencies=_dependency("catalog"))
    write_plugin("catalog")
    write_plugin("alpha")
    resolution = _resolve(plugins_dir)
    assert [candidate.key for candidate in resolution.ordered] == ["alpha", "catalog", "ecommerce"]
    assert resolution.failures == ()


def test_duplicate_keys_are_rejected(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("catalog", directory="product/catalog")
    write_plugin("catalog", directory="service/catalog_copy")
    write_plugin("other")
    resolution = _resolve(plugins_dir)
    assert [candidate.key for candidate in resolution.ordered] == ["other"]
    assert [failure.key for failure in resolution.failures] == ["catalog", "catalog"]
    assert all("more than one" in failure.error for failure in resolution.failures)


def test_missing_required_dependency_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("ecommerce", dependencies=_dependency("catalog"))
    resolution = _resolve(plugins_dir)
    assert resolution.ordered == ()
    assert "'catalog' is not available" in resolution.failures[0].error


def test_missing_optional_dependency_is_allowed(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("ecommerce", dependencies=_dependency("catalog", optional=True))
    assert [candidate.key for candidate in _resolve(plugins_dir).ordered] == ["ecommerce"]


def test_incompatible_dependency_version_is_rejected(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog", version="2.1.0")
    write_plugin("ecommerce", dependencies=_dependency("catalog", ">=1.0,<2.0"))
    resolution = _resolve(plugins_dir)
    assert [candidate.key for candidate in resolution.ordered] == ["catalog"]
    assert "2.1.0 does not satisfy" in resolution.failures[0].error


def test_failures_cascade_to_dependents(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("catalog", dependencies=_dependency("missing"))
    write_plugin("ecommerce", dependencies=_dependency("catalog"))
    resolution = _resolve(plugins_dir)
    assert resolution.ordered == ()
    assert {failure.key for failure in resolution.failures} == {"catalog", "ecommerce"}


def test_dependency_cycles_are_detected(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("first", dependencies=_dependency("second"))
    write_plugin("second", dependencies=_dependency("third"))
    write_plugin("third", dependencies=_dependency("first"))
    write_plugin("downstream", dependencies=_dependency("first"))
    write_plugin("independent")
    resolution = _resolve(plugins_dir)
    assert [candidate.key for candidate in resolution.ordered] == ["independent"]
    errors = {failure.key: failure.error for failure in resolution.failures}
    for key in ("first", "second", "third"):
        assert errors[key] == "Dependency cycle detected between: first, second, third"
    assert "failed to load" in errors["downstream"]


def test_incompatible_core_api_is_rejected(write_plugin: PluginWriter, plugins_dir: Path) -> None:
    write_plugin("future", core_api=">=2.0,<3.0")
    resolution = _resolve(plugins_dir)
    assert resolution.ordered == ()
    assert "requires core API >=2.0,<3.0" in resolution.failures[0].error
