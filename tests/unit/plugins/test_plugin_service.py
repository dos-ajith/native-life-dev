from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError, ServiceUnavailableError
from app.models.plugin import Plugin, PluginStatus
from app.plugins.loader import LoadedPlugin
from app.plugins.manifest import parse_manifest
from app.plugins.registry import PluginRegistry
from app.services.plugin_service import PluginService
from tests.unit.plugins.conftest import manifest_toml, super_admin
from tests.unit.plugins.fakes import FakeActivityLog, FakePluginRepository

REQUIRES_CATALOG = '[{ key = "catalog", version = ">=1.0,<2.0" }]'


class Harness:
    def __init__(self) -> None:
        self.plugins = FakePluginRepository()
        self.activity = FakeActivityLog()
        self.service = PluginService(cast(Session, object()))
        self.service._plugins = self.plugins  # type: ignore[assignment]
        self.service._activity_logs = self.activity  # type: ignore[assignment]
        self.loaded: list[LoadedPlugin] = []

    def add(
        self, key: str, status: PluginStatus, dependencies: str = "[]", loaded: bool = True
    ) -> Plugin:
        manifest = parse_manifest(manifest_toml(key, dependencies=dependencies).encode())
        plugin = Plugin(
            key=key,
            name=key,
            version="1.0.0",
            status=status,
            manifest=manifest.model_dump(mode="json"),
        )
        self.plugins.rows[key] = plugin
        if loaded:
            self.loaded.append(
                LoadedPlugin(
                    manifest=manifest,
                    root=Path(key),
                    content_sha256="x",
                    routers=(),
                    model_bases=(),
                )
            )
        return plugin

    @property
    def registry(self) -> PluginRegistry:
        return PluginRegistry(plugins=tuple(self.loaded))


def test_enable_requires_the_plugin_code_to_be_loaded() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.INSTALLED, loaded=False)
    with pytest.raises(BusinessRuleError, match="not loaded"):
        harness.service.enable("catalog", harness.registry, super_admin())
    assert harness.plugins.rows["catalog"].status == PluginStatus.INSTALLED
    assert harness.activity.entries == []


def test_enable_records_activity_after_success() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.INSTALLED)
    admin = super_admin()
    plugin = harness.service.enable("catalog", harness.registry, admin, "127.0.0.1", "pytest")
    assert plugin.status == PluginStatus.ENABLED
    assert plugin.enabled_at is not None
    entry = harness.activity.entries[0]
    assert entry["action"] == ActivityAction.PLUGIN_ENABLED
    assert entry["actor"] is admin
    assert entry["ip_address"] == "127.0.0.1"


def test_enable_and_disable_are_idempotent() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.ENABLED)
    harness.service.enable("catalog", harness.registry, super_admin())
    harness.add("other", PluginStatus.DISABLED)
    harness.service.disable("other", super_admin())
    assert harness.activity.entries == []


def test_enable_requires_required_dependencies_to_be_enabled() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.DISABLED)
    harness.add("ecommerce", PluginStatus.INSTALLED, dependencies=REQUIRES_CATALOG)
    with pytest.raises(BusinessRuleError, match="'catalog'"):
        harness.service.enable("ecommerce", harness.registry, super_admin())
    harness.service.enable("catalog", harness.registry, super_admin())
    assert (
        harness.service.enable("ecommerce", harness.registry, super_admin()).status
        == PluginStatus.ENABLED
    )


def test_disable_is_blocked_by_enabled_dependents() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.ENABLED)
    harness.add("ecommerce", PluginStatus.ENABLED, dependencies=REQUIRES_CATALOG)
    with pytest.raises(BusinessRuleError, match="ecommerce"):
        harness.service.disable("catalog", super_admin())
    harness.service.disable("ecommerce", super_admin())
    plugin = harness.service.disable("catalog", super_admin())
    assert plugin.status == PluginStatus.DISABLED
    assert plugin.enabled_at is None
    assert [entry["action"] for entry in harness.activity.entries] == [
        ActivityAction.PLUGIN_DISABLED,
        ActivityAction.PLUGIN_DISABLED,
    ]


def test_unknown_plugin_is_not_found() -> None:
    harness = Harness()
    with pytest.raises(NotFoundError):
        harness.service.get("missing")
    with pytest.raises(NotFoundError):
        harness.service.enable("missing", harness.registry, super_admin())


def test_ensure_serving_checks_status_and_loaded_version() -> None:
    harness = Harness()
    harness.add("catalog", PluginStatus.ENABLED)
    harness.service.ensure_serving("catalog", "1.0.0")
    with pytest.raises(ServiceUnavailableError):
        harness.service.ensure_serving("catalog", "0.9.0")
    harness.plugins.rows["catalog"].status = PluginStatus.DISABLED
    with pytest.raises(NotFoundError):
        harness.service.ensure_serving("catalog", "1.0.0")
    with pytest.raises(NotFoundError):
        harness.service.ensure_serving("missing", "1.0.0")
