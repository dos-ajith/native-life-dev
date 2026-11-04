from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.api.deps import CurrentActiveUserDep, DbSessionDep
from app.plugins.registry import PluginRegistry
from app.plugins.scoping import BusinessScope
from app.services.business_plugin_service import BusinessPluginService
from app.services.plugin_service import PluginService

EMPTY_REGISTRY = PluginRegistry()


@dataclass(frozen=True)
class PluginBusiness:
    id: UUID
    owner_id: UUID
    name: str
    category_id: UUID | None


def require_plugin_enabled(plugin_key: str, loaded_version: str) -> Callable[[DbSessionDep], None]:
    def dependency(db: DbSessionDep) -> None:
        PluginService(db).ensure_serving(plugin_key, loaded_version)

    return dependency


@dataclass(frozen=True)
class BusinessPluginAccess(BusinessScope):
    def __call__(
        self, business_id: UUID, db: DbSessionDep, user: CurrentActiveUserDep
    ) -> PluginBusiness:
        business = BusinessPluginService(db).authorize_access(business_id, self.plugin_key, user)
        return PluginBusiness(
            id=business.id,
            owner_id=business.owner_id,
            name=business.name,
            category_id=business.category_id,
        )


def require_business_plugin(plugin_key: str) -> BusinessPluginAccess:
    return BusinessPluginAccess(plugin_key)


def get_plugin_registry(request: Request) -> PluginRegistry:
    registry = getattr(request.app.state, "plugin_registry", None)
    return registry if isinstance(registry, PluginRegistry) else EMPTY_REGISTRY


PluginRegistryDep = Annotated[PluginRegistry, Depends(get_plugin_registry)]
