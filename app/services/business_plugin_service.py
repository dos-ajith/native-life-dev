from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import (
    AuthorizationError,
    BusinessRuleError,
    ConflictError,
    NotFoundError,
)
from app.core.messages import BusinessMessages, BusinessPluginMessages, PluginMessages
from app.core.permissions import PermissionName
from app.models.business import Business, BusinessStatus
from app.models.business_plugin import BusinessPlugin, BusinessPluginStatus
from app.models.category import Category
from app.models.plugin import Plugin, PluginBusinessType, PluginStatus
from app.models.user import User
from app.plugins.manifest import CapabilityDeclaration, PluginManifest
from app.plugins.registry import PluginRegistry
from app.repositories.business_plugin_repository import BusinessPluginRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.plugin_category_binding_repository import PluginCategoryBindingRepository
from app.repositories.plugin_repository import PluginRepository
from app.services.activity_log_service import ActivityLogService
from app.services.authorization_service import has_permission
from app.services.business_category_service import business_type_of, is_usable, ordered_chain
from app.services.business_service import BusinessService
from app.services.plugin_service import stored_manifest

ENTITY_TYPE = "business_plugin"
FOREIGN_KEY_VIOLATION_SQLSTATE = "23503"


def _is_foreign_key_violation(error: IntegrityError) -> bool:
    return getattr(error.orig, "sqlstate", None) == FOREIGN_KEY_VIOLATION_SQLSTATE


@dataclass(frozen=True)
class PluginOffer:
    plugin: Plugin
    manifest: PluginManifest
    business_plugin: BusinessPlugin | None

    @property
    def enabled_for_business(self) -> bool:
        return (
            self.business_plugin is not None
            and self.business_plugin.status == BusinessPluginStatus.ACTIVE
        )


@dataclass(frozen=True)
class BusinessPluginOverview:
    business: Business
    categories: list[Category]
    business_type: PluginBusinessType | None
    offers: list[PluginOffer]


def visible_capabilities(manifest: PluginManifest, viewer: User) -> list[CapabilityDeclaration]:
    return [
        capability
        for capability in manifest.capabilities
        if has_permission(viewer, capability.permission)
    ]


class BusinessPluginService:
    def __init__(self, db: Session) -> None:
        self._businesses = BusinessService(db)
        self._plugins = PluginRepository(db)
        self._bindings = PluginCategoryBindingRepository(db)
        self._business_plugins = BusinessPluginRepository(db)
        self._categories = CategoryRepository(db)
        self._activity_logs = ActivityLogService(db)

    def overview(
        self, business_id: UUID, viewer: User, registry: PluginRegistry
    ) -> BusinessPluginOverview:
        business = self._businesses.get_for_actor(business_id, viewer)
        chain = self._category_chain(business)
        return BusinessPluginOverview(
            business=business,
            categories=chain,
            business_type=business_type_of(chain),
            offers=self._offers(business, chain, registry),
        )

    def enable(
        self,
        business_id: UUID,
        plugin_key: str,
        actor: User,
        registry: PluginRegistry,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Plugin, BusinessPlugin]:
        business = self._modifiable_business(business_id, actor)
        self._ensure_verified_manager(actor)
        if business.status != BusinessStatus.ACTIVE:
            raise BusinessRuleError(BusinessMessages.INACTIVE)
        plugin = self._usable_plugin(plugin_key, registry)
        if plugin.id not in self._compatible_plugins(self._category_chain(business)):
            raise BusinessRuleError(BusinessPluginMessages.INCOMPATIBLE)
        existing = self._business_plugins.get_for_update(business.id, plugin.id)
        if existing is None:
            created = self._insert_active(business, plugin, actor)
            if created is not None:
                self._log(
                    actor,
                    ActivityAction.BUSINESS_PLUGIN_ENABLED,
                    created,
                    plugin,
                    ip_address,
                    user_agent,
                )
                return plugin, created
            existing = self._business_plugins.get_for_update(business.id, plugin.id)
            if existing is None:
                raise ConflictError(BusinessPluginMessages.ENABLE_CONFLICT)
        if existing.status == BusinessPluginStatus.ACTIVE:
            return plugin, existing
        existing.status = BusinessPluginStatus.ACTIVE
        existing.enabled_by = actor.id
        saved = self._business_plugins.save(existing)
        self._log(
            actor, ActivityAction.BUSINESS_PLUGIN_ENABLED, saved, plugin, ip_address, user_agent
        )
        return plugin, saved

    def disable(
        self,
        business_id: UUID,
        plugin_key: str,
        actor: User,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[Plugin, BusinessPlugin | None]:
        business = self._modifiable_business(business_id, actor)
        plugin = self._plugins.get_by_key(plugin_key)
        if plugin is None:
            raise NotFoundError(PluginMessages.NOT_FOUND)
        existing = self._business_plugins.get_for_update(business.id, plugin.id)
        if existing is None or existing.status == BusinessPluginStatus.DISABLED:
            return plugin, existing
        existing.status = BusinessPluginStatus.DISABLED
        saved = self._business_plugins.save(existing)
        self._log(
            actor, ActivityAction.BUSINESS_PLUGIN_DISABLED, saved, plugin, ip_address, user_agent
        )
        return plugin, saved

    def authorize_access(self, business_id: UUID, plugin_key: str, actor: User) -> Business:
        business = self._businesses.get_for_actor(business_id, actor)
        if not has_permission(actor, PermissionName.BUSINESS_VIEW_ANY):
            self._ensure_verified_manager(actor)
        if business.status != BusinessStatus.ACTIVE:
            raise BusinessRuleError(BusinessMessages.INACTIVE)
        plugin = self._plugins.get_by_key(plugin_key)
        if plugin is None or plugin.status != PluginStatus.ENABLED:
            raise NotFoundError(PluginMessages.NOT_AVAILABLE)
        business_plugin = self._business_plugins.get(business.id, plugin.id)
        if (
            business_plugin is None
            or business_plugin.status != BusinessPluginStatus.ACTIVE
            or plugin.id not in self._compatible_plugins(self._category_chain(business))
        ):
            raise AuthorizationError(BusinessPluginMessages.NOT_ENABLED_FOR_BUSINESS)
        return business

    def _insert_active(
        self, business: Business, plugin: Plugin, actor: User
    ) -> BusinessPlugin | None:
        try:
            return self._business_plugins.add_if_absent(
                BusinessPlugin(
                    business_id=business.id,
                    plugin_id=plugin.id,
                    status=BusinessPluginStatus.ACTIVE,
                    enabled_by=actor.id,
                )
            )
        except IntegrityError as exc:
            self._business_plugins.rollback()
            if not _is_foreign_key_violation(exc):
                raise
            raise ConflictError(BusinessPluginMessages.ENABLE_TARGET_REMOVED) from exc

    def _modifiable_business(self, business_id: UUID, actor: User) -> Business:
        business = self._businesses.get(business_id)
        self._businesses.ensure_can_modify(business, actor, PermissionName.BUSINESS_UPDATE_ANY)
        return business

    @staticmethod
    def _ensure_verified_manager(actor: User) -> None:
        if has_permission(actor, PermissionName.BUSINESS_UPDATE_ANY):
            return
        if not has_permission(actor, PermissionName.BUSINESS_CREATE):
            raise AuthorizationError(BusinessPluginMessages.ROLE_NOT_VERIFIED)

    def _usable_plugin(self, plugin_key: str, registry: PluginRegistry) -> Plugin:
        plugin = self._plugins.get_by_key(plugin_key)
        if plugin is None or not self._is_usable(plugin, registry):
            raise NotFoundError(PluginMessages.NOT_AVAILABLE)
        return plugin

    @staticmethod
    def _is_usable(plugin: Plugin, registry: PluginRegistry) -> bool:
        loaded = registry.get(plugin.key)
        return (
            plugin.status == PluginStatus.ENABLED
            and loaded is not None
            and str(loaded.manifest.version) == plugin.version
        )

    def _category_chain(self, business: Business) -> list[Category]:
        if business.category_id is None:
            return []
        return ordered_chain(self._categories.get_chain(business.category_id), business.category_id)

    def _compatible_plugins(self, chain: list[Category]) -> dict[UUID, Plugin]:
        business_type = business_type_of(chain)
        if business_type is None or not all(is_usable(category) for category in chain):
            return {}
        leaf_id = chain[-1].id
        rows = self._bindings.list_business_bindings_for_categories(
            [category.id for category in chain]
        )
        return {
            plugin.id: plugin
            for binding, plugin in rows
            if plugin.business_type == business_type
            and (binding.category_id == leaf_id or binding.include_descendants)
        }

    def _offers(
        self, business: Business, chain: list[Category], registry: PluginRegistry
    ) -> list[PluginOffer]:
        enabled = {
            plugin.id: business_plugin
            for business_plugin, plugin in self._business_plugins.list_for_business(business.id)
        }
        return [
            PluginOffer(
                plugin=plugin,
                manifest=stored_manifest(plugin),
                business_plugin=enabled.get(plugin.id),
            )
            for plugin in self._compatible_plugins(chain).values()
            if self._is_usable(plugin, registry)
        ]

    def _log(
        self,
        actor: User,
        action: str,
        business_plugin: BusinessPlugin,
        plugin: Plugin,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        self._activity_logs.log(
            actor=actor,
            action=action,
            entity_type=ENTITY_TYPE,
            entity_id=business_plugin.id,
            metadata={"business_id": str(business_plugin.business_id), "plugin_key": plugin.key},
            ip_address=ip_address,
            user_agent=user_agent,
        )
