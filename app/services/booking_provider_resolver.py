from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError
from app.core.messages import BookingMessages
from app.models.business_plugin import BusinessPluginStatus
from app.models.plugin import PluginStatus
from app.plugins.booking import BookingProvider
from app.plugins.loader import LoadedPlugin
from app.plugins.registry import PluginRegistry
from app.repositories.business_plugin_repository import BusinessPluginRepository
from app.repositories.plugin_repository import PluginRepository


@dataclass(frozen=True)
class ResolvedBookingProvider:
    plugin_key: str
    provider: BookingProvider


class BookingProviderResolver:
    def __init__(self, db: Session, registry: PluginRegistry | None = None) -> None:
        self._registry = registry or PluginRegistry()
        self._plugins = PluginRepository(db)
        self._business_plugins = BusinessPluginRepository(db)

    def provider_for(self, business_id: UUID) -> ResolvedBookingProvider:
        for plugin in self._registry.plugins:
            if plugin.booking_provider is not None and self._serves(plugin, business_id):
                return ResolvedBookingProvider(plugin.key, plugin.booking_provider)
        raise BusinessRuleError(BookingMessages.UNAVAILABLE)

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
