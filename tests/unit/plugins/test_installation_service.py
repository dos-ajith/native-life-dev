from pathlib import Path
from typing import cast

import pytest
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.models.plugin import PluginStatus
from app.models.plugin_installation import PluginInstallationAction, PluginInstallationStatus
from app.plugins.discovery import discover_plugins
from app.plugins.errors import PluginError
from app.services.plugin_installation_service import (
    ApplyOutcome,
    ApplyResult,
    PluginInstallationService,
)
from tests.unit.plugins.conftest import PluginWriter
from tests.unit.plugins.fakes import (
    FakeActivityLog,
    FakeCategorySync,
    FakeInstallationRepository,
    FakePermissionRepository,
    FakePluginRepository,
)


class Harness:
    def __init__(self, plugins_dir: Path, existing_permissions: set[str] | None = None) -> None:
        self.plugins_dir = plugins_dir
        self.plugins = FakePluginRepository()
        self.installations = FakeInstallationRepository()
        self.activity = FakeActivityLog()
        self.smoke_loaded: list[Path] = []
        self.rollbacks_before_smoke: list[int] = []
        self.smoke_error: str | None = None
        self.service = PluginInstallationService(cast(Session, object()), self._smoke)
        self.service._plugins = self.plugins  # type: ignore[assignment]
        self.service._installations = self.installations  # type: ignore[assignment]
        self.service._permissions = FakePermissionRepository(  # type: ignore[assignment]
            self.plugins, existing_permissions
        )
        self.service._activity_logs = self.activity  # type: ignore[assignment]
        self.category_sync = FakeCategorySync()
        self.service._category_sync = self.category_sync  # type: ignore[assignment]

    def _smoke(self, root: Path) -> None:
        self.rollbacks_before_smoke.append(self.plugins.rollbacks)
        self.smoke_loaded.append(root)
        if self.smoke_error is not None:
            raise PluginError(self.smoke_error)

    def apply(self, *keys: str) -> dict[str | None, ApplyResult]:
        results = self.service.apply(discover_plugins(self.plugins_dir), set(keys))
        return {result.key: result for result in results}


@pytest.fixture
def harness(plugins_dir: Path) -> Harness:
    return Harness(plugins_dir)


def test_first_apply_registers_metadata_and_permissions(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.INSTALLED
    row = harness.plugins.rows["catalog"]
    assert row.status == PluginStatus.INSTALLED
    assert row.version == "1.0.0"
    assert row.manifest["plugin"]["key"] == "catalog"
    assert [p.name for p in harness.plugins.created_permissions] == ["plugin.catalog.item.view"]
    installation = harness.plugins.saved_installations[0]
    assert installation.action == PluginInstallationAction.INSTALL
    assert installation.status == PluginInstallationStatus.SUCCEEDED
    assert installation.plugin_id == row.id
    assert harness.plugins.locks == 1
    assert harness.activity.entries[0]["action"] == ActivityAction.PLUGIN_INSTALLED
    assert harness.activity.entries[0]["actor"] is None
    assert len(harness.smoke_loaded) == 1


def test_reapplying_the_same_plugin_is_idempotent(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    harness.apply()
    second = harness.apply()["catalog"]
    assert second.outcome == ApplyOutcome.UNCHANGED
    assert len(harness.plugins.saved_installations) == 1
    assert len(harness.plugins.created_permissions) == 1
    assert len(harness.activity.entries) == 1
    assert harness.installations.added == []


def test_existing_permission_rows_are_not_duplicated(
    write_plugin: PluginWriter, plugins_dir: Path
) -> None:
    write_plugin("catalog")
    harness = Harness(plugins_dir, existing_permissions={"plugin.catalog.item.view"})
    assert harness.apply()["catalog"].outcome == ApplyOutcome.INSTALLED
    assert harness.plugins.created_permissions == []


def test_changed_contents_without_a_version_bump_are_rejected(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    root = write_plugin("catalog")
    harness.apply()
    original_hash = harness.plugins.rows["catalog"].content_sha256
    (root / "plugin.py").write_text((root / "plugin.py").read_text() + "\n# change\n")
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.FAILED
    assert result.message is not None and "bump the version" in result.message
    assert harness.plugins.rows["catalog"].content_sha256 == original_hash
    failure = harness.installations.added[0]
    assert failure.status == PluginInstallationStatus.FAILED
    assert failure.action == PluginInstallationAction.REAPPLY
    assert harness.plugins.rollbacks >= 1


def test_upgrade_keeps_the_enabled_status(write_plugin: PluginWriter, harness: Harness) -> None:
    write_plugin("catalog")
    harness.apply()
    harness.plugins.rows["catalog"].status = PluginStatus.ENABLED
    write_plugin("catalog", version="1.1.0")
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.UPGRADED
    row = harness.plugins.rows["catalog"]
    assert row.version == "1.1.0"
    assert row.status == PluginStatus.ENABLED
    upgrade = harness.plugins.saved_installations[-1]
    assert (upgrade.action, upgrade.from_version, upgrade.to_version) == (
        PluginInstallationAction.UPGRADE,
        "1.0.0",
        "1.1.0",
    )
    assert harness.activity.entries[-1]["action"] == ActivityAction.PLUGIN_UPGRADED


def test_downgrade_is_rejected_and_recorded(write_plugin: PluginWriter, harness: Harness) -> None:
    write_plugin("catalog", version="2.0.0")
    harness.apply()
    write_plugin("catalog", version="1.5.0")
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.FAILED
    assert harness.plugins.rows["catalog"].version == "2.0.0"
    assert harness.installations.added[0].action == PluginInstallationAction.DOWNGRADE


def test_smoke_load_failure_records_a_failed_attempt_only(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    harness.smoke_error = "Smoke load in a separate process failed: ImportError"
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.FAILED
    assert harness.plugins.rows == {}
    assert harness.activity.entries == []
    failure = harness.installations.added[0]
    assert (failure.action, failure.status, failure.plugin_id) == (
        PluginInstallationAction.INSTALL,
        PluginInstallationStatus.FAILED,
        None,
    )
    assert failure.error == harness.smoke_error


def test_plugin_migrations_are_refused_before_any_code_runs(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog", migrations=True)
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.FAILED
    assert result.message is not None and "migrations are not supported" in result.message
    assert harness.smoke_loaded == []


def test_boundary_violations_are_refused_before_any_code_runs(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog", plugin_code="from app.models.user import User\n")
    assert harness.apply()["catalog"].outcome == ApplyOutcome.FAILED
    assert harness.smoke_loaded == []


def test_dependencies_must_be_applied_first(write_plugin: PluginWriter, harness: Harness) -> None:
    write_plugin("catalog")
    write_plugin("ecommerce", dependencies='[{ key = "catalog", version = ">=1.0,<2.0" }]')
    alone = harness.apply("ecommerce")["ecommerce"]
    assert alone.outcome == ApplyOutcome.FAILED
    assert alone.message is not None and "not applied" in alone.message
    both = harness.apply()
    assert both["catalog"].outcome == ApplyOutcome.INSTALLED
    assert both["ecommerce"].outcome == ApplyOutcome.INSTALLED
    assert harness.smoke_loaded[-2].name == "catalog"


def test_key_filter_applies_only_selected_plugins(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    write_plugin("other")
    results = harness.apply("other")
    assert set(results) == {"other"}
    assert set(harness.plugins.rows) == {"other"}


def test_invalid_manifests_and_duplicate_keys_are_reported(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    broken = write_plugin("broken")
    (broken / "plugin.toml").write_text("manifest_version = 1\n")
    write_plugin("dup", directory="a/dup")
    write_plugin("dup", directory="b/dup")
    results = harness.service.apply(discover_plugins(harness.plugins_dir), set())
    outcomes = sorted((result.key or "", result.outcome) for result in results)
    assert outcomes == [
        ("", ApplyOutcome.FAILED),
        ("dup", ApplyOutcome.FAILED),
        ("dup", ApplyOutcome.FAILED),
    ]
    assert [installation.plugin_key for installation in harness.installations.added] == [
        "dup",
        "dup",
    ]
    assert harness.plugins.rows == {}


def test_read_transaction_is_released_before_the_smoke_load(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    harness.apply()
    assert harness.rollbacks_before_smoke == [1]
    assert harness.plugins.locks == 1


def test_activity_log_failure_does_not_turn_a_committed_apply_into_a_failure(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    from sqlalchemy.exc import OperationalError

    def failing_log(**_kwargs: object) -> None:
        raise OperationalError("insert", {}, Exception("log table unavailable"))

    harness.activity.log = failing_log  # type: ignore[method-assign]
    write_plugin("catalog")
    result = harness.apply()["catalog"]
    assert result.outcome == ApplyOutcome.INSTALLED
    assert "catalog" in harness.plugins.rows
    assert harness.installations.added == []


def test_duplicate_key_failures_record_each_directory(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("dup", directory="a/dup", version="1.0.0")
    write_plugin("dup", directory="b/dup", version="2.0.0")
    harness.service.apply(discover_plugins(harness.plugins_dir), set())
    assert sorted(i.to_version for i in harness.installations.added) == ["1.0.0", "2.0.0"]


def test_category_sync_runs_on_install_upgrade_and_unchanged_reapply(
    write_plugin: PluginWriter, harness: Harness
) -> None:
    write_plugin("catalog")
    harness.apply()
    harness.apply()
    write_plugin("catalog", version="1.1.0")
    harness.apply()
    assert [key for key, _ in harness.category_sync.synced] == ["catalog"] * 3
    assert harness.category_sync.logged == ["catalog"] * 3
    assert all(plugin.id is not None for plugin in harness.plugins.staged)
