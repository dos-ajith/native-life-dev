from typing import Any
from uuid import uuid4

from app.models.permission import Permission
from app.models.plugin import Plugin
from app.models.plugin_installation import PluginInstallation
from app.plugins.manifest import PluginManifest
from app.services.plugin_category_sync_service import CategorySyncResult


class FakePluginRepository:
    def __init__(self) -> None:
        self.rows: dict[str, Plugin] = {}
        self.locks = 0
        self.rollbacks = 0
        self.saved_installations: list[PluginInstallation] = []
        self.created_permissions: list[Permission] = []
        self.staged: list[Plugin] = []

    def get_by_key(self, key: str) -> Plugin | None:
        return self.rows.get(key)

    def list_all(self) -> list[Plugin]:
        return [self.rows[key] for key in sorted(self.rows)]

    def stage(self, plugin: Plugin) -> Plugin:
        self.staged.append(plugin)
        return plugin

    def lock_for_apply(self) -> None:
        self.locks += 1

    def persist_application(
        self,
        plugin: Plugin,
        permissions: list[Permission],
        installation: PluginInstallation | None,
    ) -> Plugin:
        if plugin.id is None:
            plugin.id = uuid4()
        self.rows[plugin.key] = plugin
        self.created_permissions.extend(permissions)
        if installation is not None:
            installation.plugin_id = plugin.id
            self.saved_installations.append(installation)
        return plugin

    def save(self, plugin: Plugin) -> Plugin:
        self.rows[plugin.key] = plugin
        return plugin

    def rollback(self) -> None:
        self.rollbacks += 1


class FakeInstallationRepository:
    def __init__(self) -> None:
        self.added: list[PluginInstallation] = []

    def add(self, installation: PluginInstallation) -> PluginInstallation:
        self.added.append(installation)
        return installation


class FakePermissionRepository:
    def __init__(self, plugins: FakePluginRepository, existing: set[str] | None = None) -> None:
        self._plugins = plugins
        self._existing = existing or set()

    def get_by_name(self, name: str) -> Permission | None:
        created = {permission.name for permission in self._plugins.created_permissions}
        return Permission(name=name) if name in self._existing | created else None


class FakeActivityLog:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def log(self, **kwargs: Any) -> None:
        self.entries.append(kwargs)


class FakeCategorySync:
    def __init__(self) -> None:
        self.synced: list[tuple[str, int]] = []
        self.logged: list[str] = []

    def sync(self, plugin: Plugin, manifest: PluginManifest) -> CategorySyncResult:
        self.synced.append((plugin.key, len(manifest.categories)))
        return CategorySyncResult()

    def log_result(self, plugin: Plugin, result: CategorySyncResult) -> None:
        self.logged.append(plugin.key)
