import copy
from itertools import groupby

from fastapi import APIRouter, Depends, FastAPI
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute

from app.core.openapi_tags import OPENAPI_TAGS
from app.plugins.deps import require_business_plugin, require_plugin_enabled
from app.plugins.loader import LoadedPlugin
from app.plugins.registry import PluginRegistry
from app.plugins.scoping import is_business_scoped


def _router_with(router: APIRouter, routes: list[BaseRoute]) -> APIRouter:
    group = copy.copy(router)
    group.routes = routes
    return group


def _requires_business_access(route: BaseRoute) -> bool:
    return isinstance(route, APIRoute) and is_business_scoped(route)


def mount_plugin(app: FastAPI, plugin: LoadedPlugin, api_prefix: str) -> None:
    version = str(plugin.manifest.version)
    enabled = Depends(require_plugin_enabled(plugin.key, version))
    business_access = Depends(require_business_plugin(plugin.key))
    lifespan = app.router.lifespan_context
    for router in plugin.routers:
        for scoped, routes in groupby(router.routes, key=_requires_business_access):
            app.include_router(
                _router_with(router, list(routes)),
                prefix=f"{api_prefix}{plugin.manifest.api.prefix}",
                tags=[plugin.manifest.api.tag],
                dependencies=[enabled, business_access] if scoped else [enabled],
            )
    app.router.lifespan_context = lifespan


def mount_plugins(app: FastAPI, registry: PluginRegistry, api_prefix: str) -> None:
    for plugin in registry.plugins:
        mount_plugin(app, plugin, api_prefix)
    app.openapi_tags = [*OPENAPI_TAGS, *({"name": tag} for tag in registry.openapi_tags)]
    app.state.plugin_registry = registry
