import enum
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.core.messages import PluginMessages
from app.plugins.discovery import PluginCandidate, discover_plugins
from app.plugins.errors import PluginError
from app.plugins.loader import LoadedPlugin, load_plugin
from app.plugins.resolution import resolve_load_order
from app.plugins.versioning import Version

logger = logging.getLogger("app.plugins")


class PluginLoadState(enum.StrEnum):
    LOADED = "loaded"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class AppliedPlugin:
    version: str
    content_sha256: str


@dataclass(frozen=True)
class PluginLoadOutcome:
    key: str | None
    path: str
    state: PluginLoadState
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class PluginRegistry:
    plugins: tuple[LoadedPlugin, ...] = ()
    outcomes: tuple[PluginLoadOutcome, ...] = ()

    def get(self, key: str) -> LoadedPlugin | None:
        return next((plugin for plugin in self.plugins if plugin.key == key), None)

    def outcome_for(self, key: str) -> PluginLoadOutcome | None:
        return next((outcome for outcome in self.outcomes if outcome.key == key), None)

    @property
    def openapi_tags(self) -> tuple[str, ...]:
        return tuple(plugin.manifest.api.tag for plugin in self.plugins)


def _outcome(
    candidate: PluginCandidate, state: PluginLoadState, message: str | None = None
) -> PluginLoadOutcome:
    return PluginLoadOutcome(
        key=candidate.key,
        path=str(candidate.root),
        state=state,
        version=str(candidate.manifest.version),
        message=message,
    )


def _skip_reason(candidate: PluginCandidate, applied: AppliedPlugin | None) -> str | None:
    version = str(candidate.manifest.version)
    if applied is None:
        return PluginMessages.NOT_APPLIED
    if applied.version != version:
        return PluginMessages.VERSION_NOT_APPLIED.format(version=version, applied=applied.version)
    if applied.content_sha256 != candidate.content_sha256:
        return PluginMessages.CHANGED_SINCE_APPLY.format(version=version)
    return None


def _failed_dependency(candidate: PluginCandidate, failed_keys: set[str]) -> str | None:
    return next(
        (key for key in candidate.manifest.required_dependency_keys if key in failed_keys), None
    )


def build_registry(
    plugins_dir: Path, applied: Mapping[str, AppliedPlugin], core_api_version: Version
) -> PluginRegistry:
    discovery = discover_plugins(plugins_dir)
    outcomes = [
        PluginLoadOutcome(
            key=None, path=str(failure.root), state=PluginLoadState.FAILED, message=failure.error
        )
        for failure in discovery.failures
    ]
    eligible: list[PluginCandidate] = []
    for candidate in discovery.candidates:
        reason = _skip_reason(candidate, applied.get(candidate.key))
        if reason is None:
            eligible.append(candidate)
        else:
            outcomes.append(_outcome(candidate, PluginLoadState.SKIPPED, reason))
    resolution = resolve_load_order(eligible, core_api_version)
    outcomes.extend(
        PluginLoadOutcome(
            key=failure.key,
            path=str(failure.root),
            state=PluginLoadState.FAILED,
            message=failure.error,
        )
        for failure in resolution.failures
    )
    loaded: list[LoadedPlugin] = []
    failed_keys: set[str] = set()
    for candidate in resolution.ordered:
        failed_dependency = _failed_dependency(candidate, failed_keys)
        if failed_dependency is not None:
            failed_keys.add(candidate.key)
            outcomes.append(
                _outcome(
                    candidate,
                    PluginLoadState.FAILED,
                    PluginMessages.DEPENDENCY_FAILED.format(dependency=failed_dependency),
                )
            )
            continue
        try:
            loaded.append(load_plugin(candidate))
        except PluginError as exc:
            failed_keys.add(candidate.key)
            outcomes.append(_outcome(candidate, PluginLoadState.FAILED, exc.message))
            continue
        outcomes.append(_outcome(candidate, PluginLoadState.LOADED))
    for outcome in outcomes:
        if outcome.state == PluginLoadState.FAILED:
            logger.error("Plugin %s at %s failed: %s", outcome.key, outcome.path, outcome.message)
    return PluginRegistry(plugins=tuple(loaded), outcomes=tuple(outcomes))
