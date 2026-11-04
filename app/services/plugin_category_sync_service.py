from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.business_categories import BUSINESS_TYPE_ROOT_SLUGS
from app.core.exceptions import BusinessRuleError
from app.core.messages import PluginMessages
from app.core.timezone import app_now
from app.models.category import Category, CategoryStatus
from app.models.plugin import Plugin
from app.models.plugin_category_binding import PluginCategoryBinding, PluginCategoryOwnership
from app.plugins.errors import PluginError
from app.plugins.manifest import CategoryDeclaration, PluginManifest
from app.repositories.category_repository import CategoryRepository
from app.repositories.plugin_category_binding_repository import PluginCategoryBindingRepository
from app.services.activity_log_service import ActivityLogService
from app.services.business_category_service import BusinessCategoryService, is_usable

PLUGIN_ENTITY_TYPE = "plugin"


@dataclass(frozen=True)
class CategorySyncResult:
    created_categories: tuple[Category, ...] = ()
    added: int = 0
    updated: int = 0
    removed: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.created_categories or self.added or self.updated or self.removed)


@dataclass(frozen=True)
class _ResolvedCategory:
    declaration: CategoryDeclaration
    category: Category
    created: bool


class PluginCategorySyncService:
    def __init__(self, db: Session) -> None:
        self._categories = CategoryRepository(db)
        self._bindings = PluginCategoryBindingRepository(db)
        self._business_categories = BusinessCategoryService(db)
        self._activity_logs = ActivityLogService(db)

    def sync(self, plugin: Plugin, manifest: PluginManifest) -> CategorySyncResult:
        existing = {
            binding.category_id: binding for binding in self._bindings.list_for_plugin(plugin.id)
        }
        if not manifest.categories and not existing:
            return CategorySyncResult()
        core_created, resolved = self._resolve_declared(manifest)
        added, updated = self._upsert_bindings(plugin.id, resolved, existing)
        removed = self._mark_removed(existing, {item.category.id for item in resolved})
        created = core_created + tuple(item.category for item in resolved if item.created)
        return CategorySyncResult(
            created_categories=created, added=added, updated=updated, removed=removed
        )

    def log_result(self, plugin: Plugin, result: CategorySyncResult) -> None:
        for category in result.created_categories:
            self._business_categories.log_created(category)
        if result.changed:
            self._activity_logs.log(
                actor=None,
                action=ActivityAction.PLUGIN_CATEGORIES_SYNCED,
                entity_type=PLUGIN_ENTITY_TYPE,
                entity_id=plugin.id,
                metadata={
                    "key": plugin.key,
                    "categories_created": len(result.created_categories),
                    "bindings_added": result.added,
                    "bindings_updated": result.updated,
                    "bindings_removed": result.removed,
                },
            )

    def _resolve_declared(
        self, manifest: PluginManifest
    ) -> tuple[tuple[Category, ...], list[_ResolvedCategory]]:
        if not manifest.categories:
            return (), []
        try:
            core = self._business_categories.ensure_core_categories()
        except BusinessRuleError as exc:
            raise PluginError(exc.message) from exc
        by_slug = dict(core.by_slug)
        root = by_slug[BUSINESS_TYPE_ROOT_SLUGS[manifest.plugin.business_type]]
        resolved: list[_ResolvedCategory] = []
        for declaration in manifest.categories:
            parent = by_slug[declaration.parent]
            category, created = self._resolve(declaration, parent, root)
            by_slug[declaration.slug] = category
            resolved.append(_ResolvedCategory(declaration, category, created))
        return core.created, resolved

    def _resolve(
        self, declaration: CategoryDeclaration, parent: Category, root: Category
    ) -> tuple[Category, bool]:
        existing = self._categories.get_by_slug(declaration.slug)
        if existing is not None:
            self._ensure_adoptable(existing, root)
            return existing, False
        if not is_usable(parent):
            raise PluginError(
                PluginMessages.CATEGORY_PARENT_UNUSABLE.format(
                    slug=declaration.slug, parent=parent.slug
                )
            )
        clash = self._categories.find_by_name(parent.id, declaration.name)
        if clash is not None:
            raise PluginError(
                PluginMessages.CATEGORY_NAME_CONFLICT.format(
                    name=declaration.name, parent=parent.slug, existing=clash.slug
                )
            )
        category = Category(
            id=uuid4(),
            parent_id=parent.id,
            name=declaration.name,
            slug=declaration.slug,
            status=CategoryStatus.PUBLISHED,
            is_active=True,
        )
        return self._categories.stage(category), True

    def _ensure_adoptable(self, existing: Category, root: Category) -> None:
        if existing.status != CategoryStatus.PUBLISHED:
            raise PluginError(
                PluginMessages.CATEGORY_NOT_PUBLISHED.format(
                    slug=existing.slug, status=existing.status.value
                )
            )
        chain_ids = {category.id for category in self._categories.get_chain(existing.id)}
        if root.id not in chain_ids:
            raise PluginError(
                PluginMessages.CATEGORY_OUTSIDE_SUBTREE.format(slug=existing.slug, root=root.slug)
            )

    def _upsert_bindings(
        self,
        plugin_id: UUID,
        resolved: list[_ResolvedCategory],
        existing: dict[UUID, PluginCategoryBinding],
    ) -> tuple[int, int]:
        added = updated = 0
        for item in resolved:
            binding = existing.get(item.category.id)
            if binding is None:
                self._bindings.stage(
                    PluginCategoryBinding(
                        plugin_id=plugin_id,
                        category_id=item.category.id,
                        ownership=(
                            PluginCategoryOwnership.CREATED
                            if item.created
                            else PluginCategoryOwnership.ADOPTED
                        ),
                        applies_to_businesses=item.declaration.bind,
                        include_descendants=item.declaration.include_descendants,
                    )
                )
                added += 1
                continue
            desired = (item.declaration.bind, item.declaration.include_descendants, None)
            current = (
                binding.applies_to_businesses,
                binding.include_descendants,
                binding.removed_at,
            )
            if current != desired:
                binding.applies_to_businesses = item.declaration.bind
                binding.include_descendants = item.declaration.include_descendants
                binding.removed_at = None
                updated += 1
        return added, updated

    @staticmethod
    def _mark_removed(existing: dict[UUID, PluginCategoryBinding], declared_ids: set[UUID]) -> int:
        removed = 0
        for category_id, binding in existing.items():
            if category_id not in declared_ids and binding.removed_at is None:
                binding.removed_at = app_now()
                removed += 1
        return removed
