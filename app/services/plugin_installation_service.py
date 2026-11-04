import enum
import logging
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.messages import PluginMessages
from app.models.permission import Permission
from app.models.plugin import Plugin, PluginStatus
from app.models.plugin_installation import (
    PluginInstallation,
    PluginInstallationAction,
    PluginInstallationStatus,
)
from app.plugins.boundaries import find_boundary_violations
from app.plugins.database_scripts import run_database_scripts, validate_database_scripts
from app.plugins.discovery import DiscoveryResult, PluginCandidate
from app.plugins.errors import PluginError
from app.plugins.resolution import resolve_load_order
from app.plugins.versioning import CORE_API_VERSION, Version
from app.repositories.permission_repository import PermissionRepository
from app.repositories.plugin_installation_repository import PluginInstallationRepository
from app.repositories.plugin_repository import PluginRepository
from app.services.activity_log_service import ActivityLogService
from app.services.plugin_category_sync_service import CategorySyncResult, PluginCategorySyncService

logger = logging.getLogger("app.plugins")

ENTITY_TYPE = "plugin"
INSTALLATION_ERROR_MAX_LENGTH = 2000
MAX_REPORTED_VIOLATIONS = 5


class ApplyOutcome(enum.StrEnum):
    INSTALLED = "installed"
    UPGRADED = "upgraded"
    UNCHANGED = "unchanged"
    FAILED = "failed"


@dataclass(frozen=True)
class ApplyResult:
    key: str | None
    path: str
    version: str | None
    outcome: ApplyOutcome
    message: str | None = None


def _attempted_action(existing: Plugin | None, version: Version) -> PluginInstallationAction:
    if existing is None:
        return PluginInstallationAction.INSTALL
    installed = Version.parse(existing.version)
    if version > installed:
        return PluginInstallationAction.UPGRADE
    if version == installed:
        return PluginInstallationAction.REAPPLY
    return PluginInstallationAction.DOWNGRADE


class PluginInstallationService:
    def __init__(self, db: Session, smoke_loader: Callable[[Path], None]) -> None:
        self._db = db
        self._plugins = PluginRepository(db)
        self._installations = PluginInstallationRepository(db)
        self._permissions = PermissionRepository(db)
        self._activity_logs = ActivityLogService(db)
        self._category_sync = PluginCategorySyncService(db)
        self._smoke_loader = smoke_loader

    def apply(self, discovery: DiscoveryResult, keys: Collection[str]) -> list[ApplyResult]:
        results = [
            ApplyResult(
                key=None,
                path=str(failure.root),
                version=None,
                outcome=ApplyOutcome.FAILED,
                message=failure.error,
            )
            for failure in discovery.failures
        ]
        resolution = resolve_load_order(discovery.candidates, CORE_API_VERSION)
        by_root = {candidate.root: candidate for candidate in discovery.candidates}
        for failure in resolution.failures:
            if keys and failure.key not in keys:
                continue
            candidate = by_root[failure.root]
            results.append(
                self._fail(candidate, self._plugins.get_by_key(failure.key), failure.error)
            )
        applied_in_run: dict[str, Version] = {}
        for candidate in resolution.ordered:
            if keys and candidate.key not in keys:
                continue
            result = self._apply_one(candidate, applied_in_run)
            if result.outcome != ApplyOutcome.FAILED:
                applied_in_run[candidate.key] = candidate.manifest.version
            results.append(result)
        return results

    def _apply_one(
        self, candidate: PluginCandidate, applied_in_run: Mapping[str, Version]
    ) -> ApplyResult:
        existing = self._plugins.get_by_key(candidate.key)
        try:
            self._validate(candidate, applied_in_run)
            return self._register(candidate)
        except PluginError as exc:
            self._plugins.rollback()
            return self._fail(candidate, existing, exc.message)
        except SQLAlchemyError:
            logger.exception("Database error while applying plugin %s", candidate.key)
            self._plugins.rollback()
            return self._fail(candidate, existing, PluginMessages.DATABASE_ERROR)

    def _validate(self, candidate: PluginCandidate, applied_in_run: Mapping[str, Version]) -> None:
        validate_database_scripts(candidate)
        violations = find_boundary_violations(candidate.root)
        if violations:
            raise PluginError("; ".join(violations[:MAX_REPORTED_VIOLATIONS]))
        for dependency in candidate.manifest.dependencies:
            if dependency.optional:
                continue
            version = applied_in_run.get(dependency.key) or self._installed_version(dependency.key)
            if version is None or not dependency.version_range.allows(version):
                raise PluginError(
                    PluginMessages.DEPENDENCY_NOT_APPLIED.format(dependency=dependency.key)
                )
        self._plugins.rollback()
        self._smoke_loader(candidate.root)

    def _installed_version(self, key: str) -> Version | None:
        plugin = self._plugins.get_by_key(key)
        return Version.parse(plugin.version) if plugin is not None else None

    def _register(self, candidate: PluginCandidate) -> ApplyResult:
        self._plugins.lock_for_apply()
        existing = self._plugins.get_by_key(candidate.key)
        version = candidate.manifest.version
        action = _attempted_action(existing, version)
        if action == PluginInstallationAction.DOWNGRADE and existing is not None:
            raise PluginError(
                PluginMessages.DOWNGRADE_REJECTED.format(
                    version=version, installed=existing.version
                )
            )
        if action == PluginInstallationAction.REAPPLY and existing is not None:
            if existing.content_sha256 != candidate.content_sha256:
                raise PluginError(
                    PluginMessages.CONTENT_CHANGED_WITHOUT_VERSION.format(version=version)
                )
            sync = self._category_sync.sync(existing, candidate.manifest)
            self._plugins.persist_application(existing, self._missing_permissions(candidate), None)
            self._log_category_sync(existing, sync)
            return self._result(candidate, ApplyOutcome.UNCHANGED)
        from_version = existing.version if existing is not None else None
        plugin = self._plugins.stage(self._upsert_plugin(existing, candidate))
        sync = self._category_sync.sync(plugin, candidate.manifest)
        run_database_scripts(self._db, candidate)
        installation = PluginInstallation(
            plugin_key=candidate.key,
            action=action,
            status=PluginInstallationStatus.SUCCEEDED,
            from_version=from_version,
            to_version=str(version),
            content_sha256=candidate.content_sha256,
        )
        saved = self._plugins.persist_application(
            plugin, self._missing_permissions(candidate), installation
        )
        upgraded = action == PluginInstallationAction.UPGRADE
        self._log_applied(saved, upgraded, from_version)
        self._log_category_sync(saved, sync)
        return self._result(
            candidate, ApplyOutcome.UPGRADED if upgraded else ApplyOutcome.INSTALLED
        )

    def _log_applied(self, plugin: Plugin, upgraded: bool, from_version: str | None) -> None:
        try:
            self._activity_logs.log(
                actor=None,
                action=ActivityAction.PLUGIN_UPGRADED
                if upgraded
                else ActivityAction.PLUGIN_INSTALLED,
                entity_type=ENTITY_TYPE,
                entity_id=plugin.id,
                metadata={
                    "key": plugin.key,
                    "version": plugin.version,
                    "from_version": from_version,
                },
            )
        except SQLAlchemyError:
            logger.exception("Plugin %s was applied but its activity log entry failed", plugin.key)
            self._plugins.rollback()

    def _log_category_sync(self, plugin: Plugin, sync: CategorySyncResult) -> None:
        try:
            self._category_sync.log_result(plugin, sync)
        except SQLAlchemyError:
            logger.exception("Plugin %s categories synced but logging failed", plugin.key)
            self._plugins.rollback()

    def _upsert_plugin(self, existing: Plugin | None, candidate: PluginCandidate) -> Plugin:
        manifest = candidate.manifest
        plugin = existing or Plugin(id=uuid4(), key=manifest.key, status=PluginStatus.INSTALLED)
        plugin.name = manifest.plugin.name
        plugin.business_type = manifest.plugin.business_type
        plugin.version = str(manifest.version)
        plugin.content_sha256 = candidate.content_sha256
        plugin.manifest = manifest.model_dump(mode="json")
        return plugin

    def _missing_permissions(self, candidate: PluginCandidate) -> list[Permission]:
        return [
            Permission(name=name, description=declaration.description)
            for name, declaration in sorted(candidate.manifest.permissions.items())
            if self._permissions.get_by_name(name) is None
        ]

    def _fail(self, candidate: PluginCandidate, existing: Plugin | None, error: str) -> ApplyResult:
        version = candidate.manifest.version
        self._installations.add(
            PluginInstallation(
                plugin_key=candidate.key,
                plugin_id=existing.id if existing is not None else None,
                action=_attempted_action(existing, version),
                status=PluginInstallationStatus.FAILED,
                from_version=existing.version if existing is not None else None,
                to_version=str(version),
                content_sha256=candidate.content_sha256,
                error=error[:INSTALLATION_ERROR_MAX_LENGTH],
            )
        )
        return self._result(candidate, ApplyOutcome.FAILED, error)

    @staticmethod
    def _result(
        candidate: PluginCandidate, outcome: ApplyOutcome, message: str | None = None
    ) -> ApplyResult:
        return ApplyResult(
            key=candidate.key,
            path=str(candidate.root),
            version=str(candidate.manifest.version),
            outcome=outcome,
            message=message,
        )
