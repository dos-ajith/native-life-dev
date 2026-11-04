import shutil
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import BusinessRuleError
from app.core.messages import PluginMessages
from app.models.plugin import Plugin, PluginStatus
from app.models.user import User
from app.plugins.discovery import discover_plugins
from app.plugins.errors import PluginError
from app.plugins.media import delete_plugin_media
from app.plugins.packaging import PACKAGES_DIRECTORY, package_plugin
from app.plugins.runtime import unload_from_running_app
from app.repositories.plugin_repository import PluginRepository
from app.schemas.plugin import PluginUninstallRead
from app.services.activity_log_service import ActivityLogService
from app.services.plugin_service import PluginService, stored_manifest

ENTITY_TYPE = "plugin"


class PluginUninstallService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._plugins = PluginRepository(db)
        self._lookup = PluginService(db)
        self._activity_logs = ActivityLogService(db)
        self._plugins_dir = Path(settings.plugins_dir)
        self._packages_dir = Path(PACKAGES_DIRECTORY)

    def uninstall(
        self,
        key: str,
        remove_files: bool,
        app: FastAPI,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> PluginUninstallRead:
        plugin = self._lookup.get(key)
        self._ensure_removable(plugin)
        version = plugin.version
        plugin_id = plugin.id
        root = self._plugin_root(key)
        backup = self._back_up(key) if remove_files and root is not None else None
        dropped = self._remove_records(plugin)
        delete_plugin_media(key)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.PLUGIN_UNINSTALLED,
            entity_type=ENTITY_TYPE,
            entity_id=plugin_id,
            metadata={
                "key": key,
                "version": version,
                "dropped_tables": dropped,
                "files_removed": backup is not None,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        unload_from_running_app(app, key)
        if backup is not None and root is not None:
            shutil.rmtree(root)
        return PluginUninstallRead(
            key=key,
            version=version,
            dropped_tables=dropped,
            files_removed=backup is not None,
            backup_package=str(backup) if backup is not None else None,
        )

    def _ensure_removable(self, plugin: Plugin) -> None:
        if plugin.status == PluginStatus.ENABLED:
            raise BusinessRuleError(PluginMessages.UNINSTALL_ENABLED)
        dependents = sorted(
            other.key
            for other in self._plugins.list_all()
            if other.key != plugin.key
            and plugin.key in stored_manifest(other).required_dependency_keys
        )
        if dependents:
            raise BusinessRuleError(
                PluginMessages.UNINSTALL_HAS_DEPENDENTS.format(dependents=", ".join(dependents))
            )

    def _plugin_root(self, key: str) -> Path | None:
        candidates = discover_plugins(self._plugins_dir).candidates
        return next((item.root for item in candidates if item.key == key), None)

    def _back_up(self, key: str) -> Path:
        try:
            return package_plugin(self._plugins_dir, key, self._packages_dir).path
        except (PluginError, OSError) as exc:
            message = exc.message if isinstance(exc, PluginError) else str(exc)
            raise BusinessRuleError(
                PluginMessages.UNINSTALL_BACKUP_FAILED.format(error=message)
            ) from exc

    def _remove_records(self, plugin: Plugin) -> list[str]:
        self._plugins.lock_for_apply()
        dropped = self._drop_plugin_tables(self._db.connection(), plugin.key)
        self._db.delete(plugin)
        self._db.commit()
        return dropped

    def _drop_plugin_tables(self, connection: Connection, key: str) -> list[str]:
        prefix = f"plg_{key}_"
        longer_prefixes = [
            f"plg_{other.key}_"
            for other in self._plugins.list_all()
            if other.key != key and other.key.startswith(f"{key}_")
        ]
        tables = sorted(
            name
            for name in inspect(connection).get_table_names()
            if name.startswith(prefix) and not name.startswith(tuple(longer_prefixes))
        )
        quote = connection.dialect.identifier_preparer.quote
        for name in tables:
            connection.execute(text(f"DROP TABLE IF EXISTS {quote(name)} CASCADE"))
        return tables
