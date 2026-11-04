import os
import shutil
import tempfile
from pathlib import Path
from typing import IO

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.exceptions import BusinessRuleError, NotFoundError
from app.core.messages import PluginMessages
from app.plugins.discovery import discover_plugins
from app.plugins.errors import PluginError
from app.plugins.packaging import ARCHIVE_SUFFIX, MAX_UPLOAD_BYTES, StagedPackage, staged_archive
from app.plugins.smoke import run_smoke_load
from app.plugins.versioning import Version
from app.repositories.plugin_repository import PluginRepository
from app.schemas.plugin import PluginUpgradeRead
from app.services.plugin_installation_service import ApplyOutcome, PluginInstallationService

UPLOAD_CHUNK_BYTES = 1024 * 1024
BYTES_PER_MB = 1024 * 1024
PREVIOUS_DIRECTORY = "previous"
UPLOAD_FILENAME = f"upload{ARCHIVE_SUFFIX}"


def _save_upload(upload: UploadFile, destination: IO[bytes]) -> None:
    size = 0
    while chunk := upload.file.read(UPLOAD_CHUNK_BYTES):
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise BusinessRuleError(
                PluginMessages.IMPORT_TOO_LARGE.format(limit_mb=MAX_UPLOAD_BYTES // BYTES_PER_MB)
            )
        destination.write(chunk)
    if size == 0:
        raise BusinessRuleError(PluginMessages.IMPORT_EMPTY)
    destination.flush()


class PluginUpgradeService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._plugins = PluginRepository(db)
        self._plugins_dir = Path(settings.plugins_dir)

    def upgrade(self, upload: UploadFile) -> PluginUpgradeRead:
        if not (upload.filename or "").lower().endswith(ARCHIVE_SUFFIX):
            raise BusinessRuleError(PluginMessages.IMPORT_NOT_ZIP)
        with tempfile.TemporaryDirectory() as workdir:
            archive = Path(workdir) / UPLOAD_FILENAME
            with archive.open("wb") as saved:
                _save_upload(upload, saved)
            try:
                return self._upgrade_from(archive)
            except PluginError as exc:
                raise BusinessRuleError(exc.message) from exc

    def _upgrade_from(self, archive: Path) -> PluginUpgradeRead:
        with staged_archive(self._plugins_dir, archive) as staged:
            candidate = staged.candidate
            key = candidate.key
            installed = self._plugins.get_by_key(key)
            if installed is None:
                raise NotFoundError(PluginMessages.UPGRADE_NOT_INSTALLED.format(key=key))
            if candidate.manifest.version <= Version.parse(installed.version):
                raise BusinessRuleError(
                    PluginMessages.UPGRADE_NOT_NEWER.format(
                        package=candidate.manifest.version, installed=installed.version
                    )
                )
            installed_version = installed.version
            outcome = self._swap_and_apply(key, staged)
        return PluginUpgradeRead(
            key=key,
            from_version=installed_version,
            to_version=str(candidate.manifest.version),
            outcome=outcome.value,
            restart_required=True,
            next_step=PluginMessages.UPGRADE_NEXT_STEP,
        )

    def _swap_and_apply(self, key: str, staged: StagedPackage) -> ApplyOutcome:
        existing = next(
            (
                item.root
                for item in discover_plugins(self._plugins_dir).candidates
                if item.key == key
            ),
            None,
        )
        destination = existing or (
            self._plugins_dir / staged.candidate.manifest.plugin.business_type / key
        )
        previous = staged.workspace / PREVIOUS_DIRECTORY
        if existing is not None:
            os.rename(existing, previous)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.rename(staged.path, destination)
        try:
            return self._apply(key)
        except BaseException:
            self._restore(destination, previous, existing is not None)
            raise

    def _apply(self, key: str) -> ApplyOutcome:
        discovery = discover_plugins(self._plugins_dir)
        results = PluginInstallationService(self._db, smoke_loader=run_smoke_load).apply(
            discovery, {key}
        )
        result = next((item for item in results if item.key == key), None)
        if result is None or result.outcome == ApplyOutcome.FAILED:
            raise PluginError(result.message if result and result.message else "")
        return result.outcome

    @staticmethod
    def _restore(destination: Path, previous: Path, had_previous: bool) -> None:
        shutil.rmtree(destination, ignore_errors=True)
        if had_previous:
            os.rename(previous, destination)
