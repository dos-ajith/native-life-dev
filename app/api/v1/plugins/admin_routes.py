from typing import Annotated

from fastapi import APIRouter, File, Request, UploadFile, status

from app.api.deps import ActivityRequestMetaDep, DbSessionDep, PaginationDep, SettingsDep
from app.api.v1.plugins.permissions import PluginManageDep, PluginViewDep
from app.core.messages import PluginMessages
from app.core.openapi_tags import ApiTag
from app.plugins.deps import PluginRegistryDep
from app.schemas.pagination import Page
from app.schemas.plugin import (
    PluginDetailRead,
    PluginImportRead,
    PluginLoadOutcomeRead,
    PluginRead,
    PluginUninstallRead,
    PluginUninstallRequest,
    PluginUpgradeRead,
)
from app.schemas.response import SuccessResponse
from app.services.plugin_import_service import PluginImportService
from app.services.plugin_service import PluginService, stored_manifest
from app.services.plugin_uninstall_service import PluginUninstallService
from app.services.plugin_upgrade_service import PluginUpgradeService

router = APIRouter(prefix="/admin/plugins", tags=[ApiTag.ADMIN_PLUGINS])


@router.get("", response_model=SuccessResponse[Page[PluginRead]])
def list_plugins(
    db: DbSessionDep, _: PluginViewDep, params: PaginationDep, registry: PluginRegistryDep
) -> SuccessResponse[Page[PluginRead]]:
    items, total = PluginService(db).list_page(params)
    page = Page[PluginRead].create(
        items=[PluginRead.from_plugin(item, registry) for item in items],
        total=total,
        params=params,
    )
    return SuccessResponse(message=PluginMessages.LIST_RETRIEVED, data=page)


@router.get("/load-report", response_model=SuccessResponse[list[PluginLoadOutcomeRead]])
def get_load_report(
    _: PluginViewDep, registry: PluginRegistryDep
) -> SuccessResponse[list[PluginLoadOutcomeRead]]:
    return SuccessResponse(
        message=PluginMessages.LOAD_REPORT_RETRIEVED,
        data=[PluginLoadOutcomeRead.from_outcome(outcome) for outcome in registry.outcomes],
    )


@router.post(
    "/import",
    response_model=SuccessResponse[PluginImportRead],
    status_code=status.HTTP_201_CREATED,
)
def import_plugin_package(
    request: Request,
    db: DbSessionDep,
    admin: PluginManageDep,
    settings: SettingsDep,
    meta: ActivityRequestMetaDep,
    file: Annotated[UploadFile, File()],
) -> SuccessResponse[PluginImportRead]:
    imported = PluginImportService(db, settings).import_package(
        file, request.app, admin, meta.ip_address, meta.user_agent
    )
    return SuccessResponse(message=PluginMessages.IMPORTED_INSTALLED, data=imported)


@router.get("/{plugin_key}", response_model=SuccessResponse[PluginDetailRead])
def get_plugin(
    plugin_key: str, db: DbSessionDep, _: PluginViewDep, registry: PluginRegistryDep
) -> SuccessResponse[PluginDetailRead]:
    service = PluginService(db)
    plugin = service.get(plugin_key)
    detail = PluginDetailRead.from_plugin_detail(
        plugin, stored_manifest(plugin), registry, service.recent_installations(plugin_key)
    )
    return SuccessResponse(message=PluginMessages.RETRIEVED, data=detail)


@router.post("/{plugin_key}/enable", response_model=SuccessResponse[PluginRead])
def enable_plugin(
    plugin_key: str,
    db: DbSessionDep,
    admin: PluginManageDep,
    meta: ActivityRequestMetaDep,
    registry: PluginRegistryDep,
) -> SuccessResponse[PluginRead]:
    plugin = PluginService(db).enable(plugin_key, registry, admin, meta.ip_address, meta.user_agent)
    return SuccessResponse(
        message=PluginMessages.ENABLED, data=PluginRead.from_plugin(plugin, registry)
    )


@router.post("/{plugin_key}/disable", response_model=SuccessResponse[PluginRead])
def disable_plugin(
    plugin_key: str,
    db: DbSessionDep,
    admin: PluginManageDep,
    meta: ActivityRequestMetaDep,
    registry: PluginRegistryDep,
) -> SuccessResponse[PluginRead]:
    plugin = PluginService(db).disable(plugin_key, admin, meta.ip_address, meta.user_agent)
    return SuccessResponse(
        message=PluginMessages.DISABLED, data=PluginRead.from_plugin(plugin, registry)
    )


@router.post("/upgrade", response_model=SuccessResponse[PluginUpgradeRead])
def upgrade_plugin(
    db: DbSessionDep,
    _: PluginManageDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
) -> SuccessResponse[PluginUpgradeRead]:
    upgraded = PluginUpgradeService(db, settings).upgrade(file)
    return SuccessResponse(message=PluginMessages.UPGRADED, data=upgraded)


@router.post("/{plugin_key}/uninstall", response_model=SuccessResponse[PluginUninstallRead])
def uninstall_plugin(
    plugin_key: str,
    request: Request,
    db: DbSessionDep,
    admin: PluginManageDep,
    settings: SettingsDep,
    meta: ActivityRequestMetaDep,
    payload: PluginUninstallRequest | None = None,
) -> SuccessResponse[PluginUninstallRead]:
    options = payload or PluginUninstallRequest()
    uninstalled = PluginUninstallService(db, settings).uninstall(
        plugin_key,
        options.remove_files,
        request.app,
        admin,
        meta.ip_address,
        meta.user_agent,
    )
    return SuccessResponse(message=PluginMessages.UNINSTALLED, data=uninstalled)
