import shutil
import tempfile
from pathlib import Path
from typing import IO

from fastapi import FastAPI, UploadFile
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.config import Settings
from app.core.exceptions import AppError, BusinessRuleError, ConflictError
from app.core.messages import PluginMessages
from app.models.user import User
from app.plugins.discovery import load_candidate
from app.plugins.errors import PluginConflictError, PluginError
from app.plugins.packaging import (
    ARCHIVE_SUFFIX,
    MAX_UPLOAD_BYTES,
    InstallResult,
    install_archive,
)
from app.repositories.plugin_repository import PluginRepository
from app.schemas.plugin import PluginImportRead, PluginInstallRead
from app.services.activity_log_service import ActivityLogService
from app.services.plugin_install_service import PluginInstallService

ENTITY_TYPE = "plugin"
UPLOAD_CHUNK_BYTES = 1024 * 1024
BYTES_PER_MB = 1024 * 1024
UPLOAD_FILENAME = f"upload{ARCHIVE_SUFFIX}"


class PluginImportService:
    def __init__(self, db: Session, settings: Settings) -> None:
        self._db = db
        self._settings = settings
        self._plugins = PluginRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._plugins_dir = Path(settings.plugins_dir)

    def import_package(
        self,
        upload: UploadFile,
        app: FastAPI,
        actor: User,
        ip_address: str | None,
        user_agent: str | None,
    ) -> PluginImportRead:
        if not (upload.filename or "").lower().endswith(ARCHIVE_SUFFIX):
            raise BusinessRuleError(PluginMessages.IMPORT_NOT_ZIP)
        with tempfile.TemporaryDirectory() as workdir:
            archive = Path(workdir) / UPLOAD_FILENAME
            with archive.open("wb") as saved:
                self._save_upload(upload, saved)
            result = self._install(archive)
        candidate = load_candidate(result.path)
        installed = self._install_imported(result.key, result.path, app)
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.PLUGIN_IMPORTED,
            entity_type=ENTITY_TYPE,
            metadata={"key": result.key, "version": result.version},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return PluginImportRead(
            key=result.key,
            name=candidate.manifest.plugin.name,
            version=result.version,
            business_type=candidate.manifest.plugin.business_type,
            directory=result.path.relative_to(self._plugins_dir).as_posix(),
            content_sha256=candidate.content_sha256,
            imported=True,
            applied=True,
            loaded=installed.loaded,
            enabled=False,
            next_step=installed.next_step,
        )

    def _install_imported(self, key: str, root: Path, app: FastAPI) -> PluginInstallRead:
        try:
            return PluginInstallService(self._db, self._settings).install(key, app)
        except AppError:
            shutil.rmtree(root, ignore_errors=True)
            raise

    def _save_upload(self, upload: UploadFile, destination: IO[bytes]) -> None:
        size = 0
        while chunk := upload.file.read(UPLOAD_CHUNK_BYTES):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                raise BusinessRuleError(
                    PluginMessages.IMPORT_TOO_LARGE.format(
                        limit_mb=MAX_UPLOAD_BYTES // BYTES_PER_MB
                    )
                )
            destination.write(chunk)
        if size == 0:
            raise BusinessRuleError(PluginMessages.IMPORT_EMPTY)
        destination.flush()

    def _install(self, archive: Path) -> InstallResult:
        try:
            return install_archive(
                self._plugins_dir,
                archive,
                replace=False,
                is_registered=lambda key: self._plugins.get_by_key(key) is not None,
            )
        except PluginConflictError as exc:
            raise ConflictError(exc.message) from exc
        except PluginError as exc:
            raise BusinessRuleError(exc.message) from exc
