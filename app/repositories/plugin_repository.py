from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.models.plugin import Plugin
from app.models.plugin_installation import PluginInstallation
from app.schemas.pagination import PaginationParams

PLUGIN_APPLY_ADVISORY_LOCK_ID = 727_001_202_610


class PluginRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_key(self, key: str) -> Plugin | None:
        return self._db.scalar(select(Plugin).where(Plugin.key == key))

    def list_all(self) -> list[Plugin]:
        return list(self._db.scalars(select(Plugin).order_by(Plugin.key.asc())))

    def list_page(self, params: PaginationParams) -> tuple[list[Plugin], int]:
        total = self._db.scalar(select(func.count()).select_from(Plugin)) or 0
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(Plugin).order_by(Plugin.key.asc()).offset(offset).limit(params.page_size)
        ).all()
        return list(items), total

    def stage(self, plugin: Plugin) -> Plugin:
        self._db.add(plugin)
        self._db.flush()
        return plugin

    def lock_for_apply(self) -> None:
        self._db.execute(select(func.pg_advisory_xact_lock(PLUGIN_APPLY_ADVISORY_LOCK_ID)))

    def persist_application(
        self,
        plugin: Plugin,
        permissions: list[Permission],
        installation: PluginInstallation | None,
    ) -> Plugin:
        self._db.add(plugin)
        self._db.add_all(permissions)
        self._db.flush()
        if installation is not None:
            installation.plugin_id = plugin.id
            self._db.add(installation)
        self._db.commit()
        self._db.refresh(plugin)
        return plugin

    def save(self, plugin: Plugin) -> Plugin:
        self._db.commit()
        self._db.refresh(plugin)
        return plugin

    def rollback(self) -> None:
        self._db.rollback()
