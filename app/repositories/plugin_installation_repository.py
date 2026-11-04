from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plugin_installation import PluginInstallation


class PluginInstallationRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, installation: PluginInstallation) -> PluginInstallation:
        self._db.add(installation)
        self._db.commit()
        self._db.refresh(installation)
        return installation

    def list_recent_for_key(self, plugin_key: str, limit: int) -> list[PluginInstallation]:
        return list(
            self._db.scalars(
                select(PluginInstallation)
                .where(PluginInstallation.plugin_key == plugin_key)
                .order_by(PluginInstallation.created_at.desc(), PluginInstallation.id.desc())
                .limit(limit)
            )
        )
