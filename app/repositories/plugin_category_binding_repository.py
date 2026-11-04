from collections.abc import Collection
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plugin import Plugin
from app.models.plugin_category_binding import PluginCategoryBinding


class PluginCategoryBindingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_plugin(self, plugin_id: UUID) -> list[PluginCategoryBinding]:
        return list(
            self._db.scalars(
                select(PluginCategoryBinding).where(PluginCategoryBinding.plugin_id == plugin_id)
            )
        )

    def list_business_bindings_for_categories(
        self, category_ids: Collection[UUID]
    ) -> list[tuple[PluginCategoryBinding, Plugin]]:
        rows = self._db.execute(
            select(PluginCategoryBinding, Plugin)
            .join(Plugin, Plugin.id == PluginCategoryBinding.plugin_id)
            .where(
                PluginCategoryBinding.category_id.in_(category_ids),
                PluginCategoryBinding.applies_to_businesses.is_(True),
                PluginCategoryBinding.removed_at.is_(None),
            )
            .order_by(Plugin.key.asc())
        ).all()
        return [(binding, plugin) for binding, plugin in rows]

    def stage(self, binding: PluginCategoryBinding) -> PluginCategoryBinding:
        self._db.add(binding)
        self._db.flush()
        return binding
