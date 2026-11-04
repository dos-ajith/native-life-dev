import importlib
import importlib.util
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from sqlalchemy.orm import DeclarativeBase

from app.ai.tools.base import AITool
from app.core.messages import PluginMessages
from app.models.base import Base as CoreBase
from app.plugins.boundaries import find_boundary_violations
from app.plugins.context import PluginContext
from app.plugins.deal_commerce import DealCommerceProvider
from app.plugins.discovery import PluginCandidate
from app.plugins.errors import PluginError
from app.plugins.manifest import PluginManifest
from app.plugins.metadata import configure_isolated, ensure_isolated_base
from app.plugins.scoping import (
    business_id_outside_path,
    business_scope_keys,
    is_business_scoped,
)
from app.plugins.source_imports import SourceOnlyLoader, install_plugin_source_finder

logger = logging.getLogger("app.plugins")

PACKAGE_NAME_PREFIX = "native_life_plugin_"
PACKAGE_INIT_FILENAME = "__init__.py"
MAX_REPORTED_VIOLATIONS = 5
DEFAULT_ROUTER_LIFESPAN_TYPE = type(APIRouter().lifespan_context)


@dataclass(frozen=True)
class LoadedPlugin:
    manifest: PluginManifest
    root: Path
    content_sha256: str
    routers: tuple[APIRouter, ...]
    model_bases: tuple[type[DeclarativeBase], ...]
    ai_tools: tuple[AITool[Any], ...] = ()
    deal_commerce: DealCommerceProvider | None = None

    @property
    def key(self) -> str:
        return self.manifest.key


def package_name_for(key: str) -> str:
    return f"{PACKAGE_NAME_PREFIX}{key}"


def _forget_package(package_name: str) -> None:
    for module_name in [name for name in sys.modules if name.split(".")[0] == package_name]:
        del sys.modules[module_name]


def _import_entry_module(candidate: PluginCandidate) -> ModuleType:
    init_path = candidate.root / PACKAGE_INIT_FILENAME
    if not init_path.is_file():
        raise PluginError(PluginMessages.PACKAGE_INIT_MISSING)
    package_name = package_name_for(candidate.key)
    _forget_package(package_name)
    install_plugin_source_finder(PACKAGE_NAME_PREFIX)
    spec = importlib.util.spec_from_file_location(
        package_name,
        init_path,
        loader=SourceOnlyLoader(package_name, str(init_path)),
        submodule_search_locations=[str(candidate.root)],
    )
    if spec is None or spec.loader is None:
        raise PluginError(PluginMessages.PACKAGE_INIT_MISSING)
    package = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = package
    spec.loader.exec_module(package)
    return importlib.import_module(f"{package_name}.{candidate.manifest.entrypoint.module}")


def _entrypoint(module: ModuleType, manifest: PluginManifest) -> Callable[[PluginContext], Any]:
    entrypoint = getattr(module, manifest.entrypoint.function, None)
    if not callable(entrypoint):
        raise PluginError(
            PluginMessages.ENTRYPOINT_INVALID.format(
                module=manifest.entrypoint.module, function=manifest.entrypoint.function
            )
        )
    return cast(Callable[[PluginContext], Any], entrypoint)


def _ensure_no_route_tags(routers: tuple[APIRouter, ...]) -> None:
    for router in routers:
        if router.tags or any(
            isinstance(route, APIRoute) and route.tags for route in router.routes
        ):
            raise PluginError(PluginMessages.ROUTE_TAGS_FORBIDDEN)


def _ensure_no_lifecycle_hooks(routers: tuple[APIRouter, ...]) -> None:
    for router in routers:
        has_custom_lifespan = not isinstance(router.lifespan_context, DEFAULT_ROUTER_LIFESPAN_TYPE)
        if router.on_startup or router.on_shutdown or has_custom_lifespan:
            raise PluginError(PluginMessages.ROUTER_LIFECYCLE_FORBIDDEN)


def _ensure_standard_routes(routers: tuple[APIRouter, ...]) -> None:
    for router in routers:
        for route in router.routes:
            if type(route) is not APIRoute:
                raise PluginError(
                    PluginMessages.UNSUPPORTED_ROUTE_TYPE.format(
                        path=getattr(route, "path", ""), kind=type(route).__name__
                    )
                )


def _ensure_business_routes_scoped(plugin_key: str, routers: tuple[APIRouter, ...]) -> None:
    for router in routers:
        for route in router.routes:
            if not isinstance(route, APIRoute):
                continue
            keys = business_scope_keys(route.dependant)
            foreign = sorted(keys - {plugin_key})
            if foreign:
                raise PluginError(
                    PluginMessages.FOREIGN_BUSINESS_PLUGIN_KEY.format(
                        path=route.path, key=foreign[0]
                    )
                )
            if keys and not is_business_scoped(route):
                raise PluginError(
                    PluginMessages.BUSINESS_DEPENDENCY_OUTSIDE_SCOPE.format(path=route.path)
                )
            locations = sorted(business_id_outside_path(route.dependant))
            if locations:
                raise PluginError(
                    PluginMessages.BUSINESS_ID_NOT_IN_PATH.format(
                        path=route.path, location=locations[0]
                    )
                )


def _ensure_openapi_generates(manifest: PluginManifest, routers: tuple[APIRouter, ...]) -> None:
    trial = FastAPI()
    try:
        for router in routers:
            trial.include_router(router, prefix=manifest.api.prefix, tags=[manifest.api.tag])
        trial.openapi()
    except Exception as exc:
        raise PluginError(
            PluginMessages.OPENAPI_GENERATION_FAILED.format(error=type(exc).__name__)
        ) from exc


def _plugin_classes(package_name: str) -> list[type]:
    modules = [
        module for name, module in list(sys.modules.items()) if name.split(".")[0] == package_name
    ]
    return [
        value
        for module in modules
        for value in vars(module).values()
        if isinstance(value, type) and value.__module__.split(".")[0] == package_name
    ]


def _ensure_models_registered(
    package_name: str, model_bases: tuple[type[DeclarativeBase], ...]
) -> None:
    for cls in _plugin_classes(package_name):
        if issubclass(cls, CoreBase):
            raise PluginError(PluginMessages.MODEL_BASE_NOT_ISOLATED)
        if DeclarativeBase in cls.__bases__ and cls not in model_bases:
            raise PluginError(PluginMessages.MODELS_NOT_REGISTERED.format(name=cls.__name__))


def _ensure_boundaries(candidate: PluginCandidate) -> None:
    violations = find_boundary_violations(candidate.root)
    if violations:
        raise PluginError("; ".join(violations[:MAX_REPORTED_VIOLATIONS]))


def _register(candidate: PluginCandidate) -> LoadedPlugin:
    try:
        module = _import_entry_module(candidate)
    except PluginError:
        raise
    except (Exception, SystemExit) as exc:
        raise PluginError(PluginMessages.IMPORT_FAILED.format(error=type(exc).__name__)) from exc
    entrypoint = _entrypoint(module, candidate.manifest)
    context = PluginContext(candidate.manifest)
    try:
        entrypoint(context)
    except PluginError:
        raise
    except (Exception, SystemExit) as exc:
        raise PluginError(PluginMessages.REGISTER_FAILED.format(error=type(exc).__name__)) from exc
    contribution = context.close()
    _ensure_standard_routes(contribution.routers)
    _ensure_no_route_tags(contribution.routers)
    _ensure_no_lifecycle_hooks(contribution.routers)
    _ensure_business_routes_scoped(candidate.key, contribution.routers)
    _ensure_openapi_generates(candidate.manifest, contribution.routers)
    _ensure_models_registered(package_name_for(candidate.key), contribution.model_bases)
    for base in contribution.model_bases:
        ensure_isolated_base(base, candidate.manifest.database.table_prefix)
        configure_isolated(base)
    return LoadedPlugin(
        manifest=candidate.manifest,
        root=candidate.root,
        content_sha256=candidate.content_sha256,
        routers=contribution.routers,
        model_bases=contribution.model_bases,
        ai_tools=contribution.ai_tools,
        deal_commerce=contribution.deal_commerce,
    )


def load_plugin(candidate: PluginCandidate) -> LoadedPlugin:
    _ensure_boundaries(candidate)
    try:
        return _register(candidate)
    except PluginError:
        logger.exception("Plugin %s failed to load", candidate.key)
        _forget_package(package_name_for(candidate.key))
        raise
