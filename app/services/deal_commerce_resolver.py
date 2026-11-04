from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import DealMessages
from app.models.business_plugin import BusinessPluginStatus
from app.models.plugin import PluginStatus
from app.plugins.deal_commerce import DealCommerceProvider
from app.plugins.loader import LoadedPlugin
from app.plugins.registry import PluginRegistry
from app.repositories.business_plugin_repository import BusinessPluginRepository
from app.repositories.plugin_repository import PluginRepository


class DealCommerceResolver:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._registry = registry or PluginRegistry()
        self._plugins = PluginRepository(db)
        self._business_plugins = BusinessPluginRepository(db)

    def provider_for(self, business_id: UUID) -> DealCommerceProvider:
        for plugin in self._registry.plugins:
            if plugin.deal_commerce is not None and self._serves(plugin, business_id):
                return plugin.deal_commerce
        raise BusinessRuleError(DealMessages.COMMERCE_UNAVAILABLE)

    def _serves(self, plugin: LoadedPlugin, business_id: UUID) -> bool:
        stored = self._plugins.get_by_key(plugin.key)
        if (
            stored is None
            or stored.status != PluginStatus.ENABLED
            or stored.version != str(plugin.manifest.version)
        ):
            return False
        association = self._business_plugins.get(business_id, stored.id)
        return association is not None and association.status == BusinessPluginStatus.ACTIVE
