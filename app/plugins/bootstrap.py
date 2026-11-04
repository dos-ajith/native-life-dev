import logging
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.messages import PluginMessages
from app.plugins.registry import PluginLoadOutcome, PluginLoadState, PluginRegistry, build_registry
from app.plugins.versioning import CORE_API_VERSION
from app.services.plugin_service import PluginService

logger = logging.getLogger("app.plugins")


def _unavailable_registry(plugins_dir: str) -> PluginRegistry:
    return PluginRegistry(
        outcomes=(
            PluginLoadOutcome(
                key=None,
                path=plugins_dir,
                state=PluginLoadState.FAILED,
                message=PluginMessages.REGISTRY_UNAVAILABLE,
            ),
        )
    )


def load_plugin_registry(db: Session, settings: Settings) -> PluginRegistry:
    try:
        applied = PluginService(db).applied_snapshot()
        return build_registry(Path(settings.plugins_dir), applied, CORE_API_VERSION)
    except Exception:
        logger.exception("Plugin bootstrap failed; continuing without plugins")
        db.rollback()
        return _unavailable_registry(settings.plugins_dir)
