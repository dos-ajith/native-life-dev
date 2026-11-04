from pathlib import Path

from app.plugins.discovery import discover_plugins, load_candidate, plugin_content_sha256
from tests.unit.plugins.conftest import PluginWriter


def test_missing_directory_discovers_nothing(tmp_path: Path) -> None:
    result = discover_plugins(tmp_path / "does-not-exist")
    assert result.candidates == ()
    assert result.failures == ()


def test_identity_comes_from_the_manifest_not_the_directory(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog", directory="service/totally-different-name")
    result = discover_plugins(plugins_dir)
    assert [candidate.key for candidate in result.candidates] == ["catalog"]
    assert str(result.candidates[0].manifest.plugin.business_type) == "product"


def test_invalid_manifest_is_reported_without_hiding_valid_plugins(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog")
    broken = write_plugin("broken")
    (broken / "plugin.toml").write_text("manifest_version = 1\n")
    result = discover_plugins(plugins_dir)
    assert [candidate.key for candidate in result.candidates] == ["catalog"]
    assert len(result.failures) == 1
    assert result.failures[0].root == broken


def test_manifests_inside_tests_directories_are_ignored(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog")
    write_plugin("fixture", directory="catalog/tests/fixture")
    assert [candidate.key for candidate in discover_plugins(plugins_dir).candidates] == ["catalog"]


def test_content_hash_tracks_code_but_not_caches_or_tests(write_plugin: PluginWriter) -> None:
    root = write_plugin("catalog")
    original = plugin_content_sha256(root)
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "plugin.cpython-312.pyc").write_bytes(b"cache")
    (root / "tests").mkdir()
    (root / "tests" / "test_catalog.py").write_text("x = 1\n")
    assert plugin_content_sha256(root) == original
    (root / "plugin.py").write_text("changed = True\n")
    assert plugin_content_sha256(root) != original
    assert load_candidate(root).content_sha256 == plugin_content_sha256(root)
