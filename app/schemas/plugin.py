from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.plugin import Plugin, PluginBusinessType, PluginStatus
from app.models.plugin_installation import (
    PluginInstallation,
    PluginInstallationAction,
    PluginInstallationStatus,
)
from app.plugins.manifest import PluginManifest
from app.plugins.registry import PluginLoadOutcome, PluginLoadState, PluginRegistry
from app.schemas.base import BaseReadSchema


class PluginRead(BaseReadSchema):
    id: UUID
    key: str
    name: str
    version: str
    business_type: PluginBusinessType
    status: PluginStatus
    enabled_at: datetime | None
    load_state: PluginLoadState | None
    load_message: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_plugin(cls, plugin: Plugin, registry: PluginRegistry) -> "PluginRead":
        outcome = registry.outcome_for(plugin.key)
        return cls(
            id=plugin.id,
            key=plugin.key,
            name=plugin.name,
            version=plugin.version,
            business_type=plugin.business_type,
            status=plugin.status,
            enabled_at=plugin.enabled_at,
            load_state=outcome.state if outcome is not None else None,
            load_message=outcome.message if outcome is not None else None,
            created_at=plugin.created_at,
            updated_at=plugin.updated_at,
        )


class PluginDependencyRead(BaseModel):
    key: str
    version: str
    optional: bool


class PluginCategoryRead(BaseModel):
    slug: str
    name: str
    parent: str
    bind: bool
    include_descendants: bool


class PluginInstallationRead(BaseReadSchema):
    id: UUID
    action: PluginInstallationAction
    status: PluginInstallationStatus
    from_version: str | None
    to_version: str
    error: str | None
    created_at: datetime


class PluginDetailRead(PluginRead):
    description: str | None
    role_scope: str
    api_prefix: str
    dependencies: list[PluginDependencyRead]
    categories: list[PluginCategoryRead]
    permissions: list[str]
    installations: list[PluginInstallationRead]

    @classmethod
    def from_plugin_detail(
        cls,
        plugin: Plugin,
        manifest: PluginManifest,
        registry: PluginRegistry,
        installations: list[PluginInstallation],
    ) -> "PluginDetailRead":
        base = PluginRead.from_plugin(plugin, registry)
        return cls(
            **{name: getattr(base, name) for name in PluginRead.model_fields},
            description=manifest.plugin.description,
            role_scope=manifest.plugin.role_scope,
            api_prefix=manifest.api.prefix,
            dependencies=[
                PluginDependencyRead.model_validate(dependency.model_dump())
                for dependency in manifest.dependencies
            ],
            categories=[
                PluginCategoryRead.model_validate(category.model_dump())
                for category in manifest.categories
            ],
            permissions=sorted(manifest.permissions),
            installations=[
                PluginInstallationRead.model_validate(installation)
                for installation in installations
            ],
        )


class PluginLoadOutcomeRead(BaseModel):
    key: str | None
    path: str
    state: PluginLoadState
    version: str | None
    message: str | None

    @classmethod
    def from_outcome(cls, outcome: PluginLoadOutcome) -> "PluginLoadOutcomeRead":
        return cls(
            key=outcome.key,
            path=outcome.path,
            state=outcome.state,
            version=outcome.version,
            message=outcome.message,
        )


class PluginImportRead(BaseModel):
    key: str
    name: str
    version: str
    business_type: PluginBusinessType
    directory: str
    content_sha256: str
    imported: bool
    applied: bool
    loaded: bool
    enabled: bool
    next_step: str


class PluginInstallRead(BaseModel):
    key: str
    version: str
    outcome: str
    loaded: bool
    enabled: bool
    next_step: str


class PluginUninstallRequest(BaseModel):
    remove_files: bool = True


class PluginUninstallRead(BaseModel):
    key: str
    version: str
    dropped_tables: list[str]
    files_removed: bool
    backup_package: str | None


class PluginUpgradeRead(BaseModel):
    key: str
    from_version: str
    to_version: str
    outcome: str
    restart_required: bool
    next_step: str
