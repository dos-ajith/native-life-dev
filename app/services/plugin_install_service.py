from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PluginMessages
from app.plugins.discovery import PluginCandidate, discover_plugins
from app.plugins.errors import PluginError
from app.plugins.runtime import load_into_running_app
from app.plugins.smoke import run_smoke_load
from app.schemas.plugin import PluginInstallRead
from app.services.plugin_installation_service import ApplyOutcome, PluginInstallationService


class PluginInstallService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._plugins_dir = Path(settings.plugins_dir)
        self._api_prefix = settings.api_v1_prefix

    def install(self, key: str, app: FastAPI) -> PluginInstallRead:
        discovery = discover_plugins(self._plugins_dir)
        candidate = next((item for item in discovery.candidates if item.key == key), None)
        if candidate is None:
            raise NotFoundError(PluginMessages.NOT_IMPORTED.format(key=key))
        results = PluginInstallationService(self._db, smoke_loader=run_smoke_load).apply(
            discovery, {key}
        )
        result = next((item for item in results if item.key == key), None)
        if result is None or result.outcome == ApplyOutcome.FAILED:
            raise BusinessRuleError(result.message if result and result.message else "")
        loaded, next_step = self._load(app, candidate)
        return PluginInstallRead(
            key=key,
            version=str(candidate.manifest.version),
            outcome=result.outcome.value,
            loaded=loaded,
            enabled=False,
            next_step=next_step,
        )

    def _load(self, app: FastAPI, candidate: PluginCandidate) -> tuple[bool, str]:
        try:
            load_into_running_app(app, candidate, self._api_prefix)
        except PluginError as exc:
            return False, PluginMessages.INSTALLED_RESTART.format(reason=exc.message)
        return True, PluginMessages.INSTALLED_LOADED
