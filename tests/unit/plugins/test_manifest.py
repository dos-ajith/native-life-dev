import pytest

from app.models.plugin import PluginBusinessType
from app.plugins.errors import PluginError
from app.plugins.manifest import load_manifest, parse_manifest
from tests.unit.plugins.conftest import REFERENCE_PLUGIN_ROOT, manifest_toml


def test_reference_plugin_manifest_is_valid() -> None:
    manifest = load_manifest(REFERENCE_PLUGIN_ROOT / "plugin.toml")
    assert manifest.key == "hello"
    assert str(manifest.version) == "1.1.0"
    assert manifest.plugin.business_type == PluginBusinessType.SERVICE
    assert manifest.api.prefix == "/plugins/hello"
    assert manifest.database.table_prefix == "plg_hello_"
    assert set(manifest.permissions) == {"plugin.hello.greeting.view"}
    assert [category.slug for category in manifest.categories] == ["business-service-reference"]
    assert [capability.key for capability in manifest.capabilities] == ["business_greeting"]


def test_generated_manifest_is_valid() -> None:
    manifest = parse_manifest(manifest_toml("catalog").encode())
    assert manifest.key == "catalog"
    assert manifest.dependencies == ()


def _replace(key: str, old: str, new: str) -> bytes:
    text = manifest_toml(key)
    assert old in text
    return text.replace(old, new).encode()


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (b'unexpected = "x"\n' + manifest_toml("catalog").encode(), "Extra inputs"),
        (manifest_toml("catalog", extra='unexpected = "x"\n').encode(), "Extra inputs"),
        (manifest_toml("catalog", role_scope="promoter").encode(), "business-service-provider"),
        (manifest_toml("catalog", version="1.0").encode(), "semantic version"),
        (manifest_toml("catalog", core_api="latest").encode(), "version range"),
        (manifest_toml("Catalog").encode(), "Plugin key"),
        (manifest_toml("ab").encode(), "Plugin key"),
        (manifest_toml("bad__key").encode(), "Plugin key"),
        (_replace("catalog", 'prefix = "/plugins/catalog"', 'prefix = "/catalog"'), "api.prefix"),
        (
            _replace(
                "catalog", 'prefix = "/plugins/catalog"', 'prefix = "/api/v1/plugins/catalog"'
            ),
            "api.prefix",
        ),
        (
            _replace("catalog", 'tag = "1.5 Businesses · catalog"', 'tag = "Catalog"'),
            "api.tag",
        ),
        (
            _replace("catalog", 'table_prefix = "plg_catalog_"', 'table_prefix = "catalog_"'),
            "table_prefix",
        ),
        (
            _replace("catalog", '"plugin.catalog.item.view"', '"plugin.other.item.view"'),
            "must look like",
        ),
        (
            _replace("catalog", '"plugin.catalog.item.view"', '"plugin.catalog.view"'),
            "must look like",
        ),
        (_replace("catalog", '"plugin.catalog.item.view"', '"business.create"'), "must look like"),
        (_replace("catalog", "manifest_version = 1", "manifest_version = 2"), "manifest_version"),
        (_replace("catalog", "categories = []\n", ""), "categories"),
        (_replace("catalog", "dependencies = []\n", ""), "dependencies"),
        (b"not = [valid", "Could not read"),
    ],
)
def test_invalid_manifests_are_rejected(content: bytes, expected: str) -> None:
    with pytest.raises(PluginError) as error:
        parse_manifest(content)
    assert expected in error.value.message


def test_self_and_duplicate_dependencies_are_rejected() -> None:
    self_dependency = manifest_toml(
        "catalog", dependencies='[{ key = "catalog", version = ">=1.0" }]'
    )
    with pytest.raises(PluginError, match="cannot depend on itself"):
        parse_manifest(self_dependency.encode())
    duplicate = manifest_toml(
        "catalog",
        dependencies='[{ key = "base", version = ">=1.0" }, { key = "base", version = ">=1.0" }]',
    )
    with pytest.raises(PluginError, match="more than once"):
        parse_manifest(duplicate.encode())


def _with_categories(categories: str) -> bytes:
    return manifest_toml("catalog").replace("categories = []", categories).encode()


def test_categories_must_live_under_the_business_type_root() -> None:
    valid = _with_categories(
        "categories = [\n"
        '  { slug = "business-product-ecommerce", name = "E-commerce", '
        'parent = "business-product", bind = true },\n'
        '  { slug = "business-product-ecommerce-organic", name = "Organic", '
        'parent = "business-product-ecommerce" },\n'
        "]"
    )
    manifest = parse_manifest(valid)
    assert [category.slug for category in manifest.categories] == [
        "business-product-ecommerce",
        "business-product-ecommerce-organic",
    ]
    wrong_root = _with_categories(
        'categories = [{ slug = "business-service-hotel", name = "Hotel", '
        'parent = "business-service" }]'
    )
    with pytest.raises(PluginError, match="must start with 'business-product-'"):
        parse_manifest(wrong_root)
    unknown_parent = _with_categories(
        'categories = [{ slug = "business-product-a", name = "A", '
        'parent = "business-product-zzz" }]'
    )
    with pytest.raises(PluginError, match="unknown|neither"):
        parse_manifest(unknown_parent)


def test_entrypoint_cannot_live_in_the_tests_package() -> None:
    content = manifest_toml("catalog", extra='\n[entrypoint]\nmodule = "tests.evil"\n')
    with pytest.raises(PluginError, match="must not be inside 'tests'"):
        parse_manifest(content.encode())


def test_version_cannot_exceed_the_column_length() -> None:
    with pytest.raises(PluginError, match="plugin.version"):
        parse_manifest(manifest_toml("catalog", version="1.0." + "9" * 60).encode())
