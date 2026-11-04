from dataclasses import replace

from fastapi import FastAPI

from app.core.messages import PluginMessages
from app.plugins.discovery import PluginCandidate
from app.plugins.errors import PluginError
from app.plugins.loader import load_plugin
from app.plugins.mounting import mount_plugin
from app.plugins.registry import PluginLoadOutcome, PluginLoadState, PluginRegistry


def _current_registry(app: FastAPI) -> PluginRegistry:
    registry = getattr(app.state, "plugin_registry", None)
    return registry if isinstance(registry, PluginRegistry) else PluginRegistry()


def load_into_running_app(
    app: FastAPI, candidate: PluginCandidate, api_prefix: str
) -> PluginLoadOutcome:
    registry = _current_registry(app)
    if registry.get(candidate.key) is not None:
        return PluginLoadOutcome(
            key=candidate.key,
            path=str(candidate.root),
            state=PluginLoadState.LOADED,
            version=str(candidate.manifest.version),
        )
    loaded_keys = {plugin.key for plugin in registry.plugins}
    missing = [key for key in candidate.manifest.required_dependency_keys if key not in loaded_keys]
    if missing:
        raise PluginError(PluginMessages.DEPENDENCY_NOT_LOADED.format(dependency=missing[0]))
    loaded = load_plugin(candidate)
    mount_plugin(app, loaded, api_prefix)
    tag = loaded.manifest.api.tag
    if all(entry.get("name") != tag for entry in app.openapi_tags or []):
        app.openapi_tags = [*(app.openapi_tags or []), {"name": tag}]
    app.openapi_schema = None
    outcome = PluginLoadOutcome(
        key=candidate.key,
        path=str(candidate.root),
        state=PluginLoadState.LOADED,
        version=str(candidate.manifest.version),
    )
    app.state.plugin_registry = replace(
        registry,
        plugins=(*registry.plugins, loaded),
        outcomes=(*(o for o in registry.outcomes if o.key != candidate.key), outcome),
    )
    return outcome


def unload_from_running_app(app: FastAPI, key: str) -> None:
    registry = _current_registry(app)
    app.state.plugin_registry = replace(
        registry,
        plugins=tuple(plugin for plugin in registry.plugins if plugin.key != key),
        outcomes=tuple(outcome for outcome in registry.outcomes if outcome.key != key),
    )
