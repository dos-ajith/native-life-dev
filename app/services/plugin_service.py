from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import BusinessRuleError, NotFoundError, ServiceUnavailableError
from app.core.messages import PluginMessages
from app.core.timezone import app_now
from app.models.plugin import Plugin, PluginStatus
from app.models.plugin_installation import PluginInstallation
from app.models.user import User
from app.plugins.manifest import PluginManifest
from app.plugins.registry import AppliedPlugin, PluginRegistry
from app.repositories.plugin_installation_repository import PluginInstallationRepository
from app.repositories.plugin_repository import PluginRepository
from app.schemas.pagination import PaginationParams
from app.services.activity_log_service import ActivityLogService

ENTITY_TYPE = "plugin"
RECENT_INSTALLATIONS_LIMIT = 20


def stored_manifest(plugin: Plugin) -> PluginManifest:
    return PluginManifest.model_validate(plugin.manifest)


class PluginService:
    def __init__(self, db: Session) -> None:
        self._plugins = PluginRepository(db)
        self._installations = PluginInstallationRepository(db)
        self._activity_logs = ActivityLogService(db)

    def applied_snapshot(self) -> dict[str, AppliedPlugin]:
        return {
            plugin.key: AppliedPlugin(version=plugin.version, content_sha256=plugin.content_sha256)
            for plugin in self._plugins.list_all()
        }

    def ensure_serving(self, key: str, loaded_version: str) -> None:
        plugin = self._plugins.get_by_key(key)
        if plugin is None or plugin.status != PluginStatus.ENABLED:
            raise NotFoundError(PluginMessages.NOT_AVAILABLE)
        if plugin.version != loaded_version:
            raise ServiceUnavailableError(PluginMessages.RESTART_REQUIRED)

    def list_page(self, params: PaginationParams) -> tuple[list[Plugin], int]:
        return self._plugins.list_page(params)

    def get(self, key: str) -> Plugin:
        plugin = self._plugins.get_by_key(key)
        if plugin is None:
            raise NotFoundError(PluginMessages.NOT_FOUND)
        return plugin

    def recent_installations(self, key: str) -> list[PluginInstallation]:
        return self._installations.list_recent_for_key(key, RECENT_INSTALLATIONS_LIMIT)

    def enable(
        self,
        key: str,
        registry: PluginRegistry,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Plugin:
        plugin = self.get(key)
        if plugin.status == PluginStatus.ENABLED:
            return plugin
        loaded = registry.get(key)
        if loaded is None or str(loaded.manifest.version) != plugin.version:
            raise BusinessRuleError(PluginMessages.NOT_LOADED)
        self._ensure_dependencies_enabled(stored_manifest(plugin))
        plugin.status = PluginStatus.ENABLED
        plugin.enabled_at = app_now()
        saved = self._plugins.save(plugin)
        self._log(actor, ActivityAction.PLUGIN_ENABLED, saved, ip_address, user_agent)
        return saved

    def disable(
        self,
        key: str,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> Plugin:
        plugin = self.get(key)
        if plugin.status != PluginStatus.ENABLED:
            return plugin
        self._ensure_no_enabled_dependents(plugin.key)
        plugin.status = PluginStatus.DISABLED
        plugin.enabled_at = None
        saved = self._plugins.save(plugin)
        self._log(actor, ActivityAction.PLUGIN_DISABLED, saved, ip_address, user_agent)
        return saved

    def _ensure_dependencies_enabled(self, manifest: PluginManifest) -> None:
        for dependency_key in manifest.required_dependency_keys:
            dependency = self._plugins.get_by_key(dependency_key)
            if dependency is None or dependency.status != PluginStatus.ENABLED:
                raise BusinessRuleError(
                    PluginMessages.DEPENDENCY_NOT_ENABLED.format(dependency=dependency_key)
                )

    def _ensure_no_enabled_dependents(self, key: str) -> None:
        dependents = sorted(
            other.key
            for other in self._plugins.list_all()
            if other.status == PluginStatus.ENABLED
            and key in stored_manifest(other).required_dependency_keys
        )
        if dependents:
            raise BusinessRuleError(
                PluginMessages.HAS_ENABLED_DEPENDENTS.format(dependents=", ".join(dependents))
            )

    def _log(
        self,
        actor: User,
        action: str,
        plugin: Plugin,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=plugin.id,
            metadata={"key": plugin.key, "version": plugin.version},
            ip_address=ip_address,
            user_agent=user_agent,
        )
