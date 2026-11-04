from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.core.messages import PluginMessages
from app.plugins.discovery import PluginCandidate
from app.plugins.versioning import Version


@dataclass(frozen=True)
class ResolutionFailure:
    key: str
    root: Path
    error: str


@dataclass(frozen=True)
class Resolution:
    ordered: tuple[PluginCandidate, ...]
    failures: tuple[ResolutionFailure, ...]


def _dependency_error(
    candidate: PluginCandidate, available: Mapping[str, PluginCandidate]
) -> str | None:
    for dependency in candidate.manifest.dependencies:
        provider = available.get(dependency.key)
        if provider is None:
            if dependency.optional:
                continue
            return PluginMessages.MISSING_DEPENDENCY.format(dependency=dependency.key)
        if not dependency.version_range.allows(provider.manifest.version):
            return PluginMessages.INCOMPATIBLE_DEPENDENCY.format(
                dependency=dependency.key,
                version=provider.manifest.version,
                required=dependency.version,
            )
    return None


def _drop_unsatisfied(
    candidates: dict[str, PluginCandidate], failures: list[ResolutionFailure]
) -> None:
    changed = True
    while changed:
        changed = False
        for key, candidate in sorted(candidates.items()):
            error = _dependency_error(candidate, candidates)
            if error is not None:
                failures.append(ResolutionFailure(key=key, root=candidate.root, error=error))
                del candidates[key]
                changed = True


def _edges(candidates: Mapping[str, PluginCandidate]) -> dict[str, set[str]]:
    return {
        key: {dep.key for dep in candidate.manifest.dependencies if dep.key in candidates}
        for key, candidate in candidates.items()
    }


def _reaches_itself(start: str, edges: Mapping[str, set[str]], within: set[str]) -> bool:
    stack = [dependency for dependency in edges[start] if dependency in within]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == start:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(dependency for dependency in edges[current] if dependency in within)
    return False


def _topological_order(
    candidates: dict[str, PluginCandidate], failures: list[ResolutionFailure]
) -> list[PluginCandidate]:
    edges = _edges(candidates)
    remaining = {key: set(dependencies) for key, dependencies in edges.items()}
    ordered: list[PluginCandidate] = []
    ready = sorted(key for key, dependencies in remaining.items() if not dependencies)
    while ready:
        key = ready.pop(0)
        ordered.append(candidates[key])
        del remaining[key]
        for other, dependencies in remaining.items():
            if key in dependencies:
                dependencies.discard(key)
                if not dependencies and other not in ready:
                    ready.append(other)
        ready.sort()
    blocked = set(remaining)
    cycle_members = sorted(key for key in blocked if _reaches_itself(key, edges, blocked))
    for key in sorted(blocked):
        if key in cycle_members:
            error = PluginMessages.DEPENDENCY_CYCLE.format(keys=", ".join(cycle_members))
        else:
            dependency = sorted(edges[key] & blocked)[0]
            error = PluginMessages.DEPENDENCY_FAILED.format(dependency=dependency)
        failures.append(ResolutionFailure(key=key, root=candidates[key].root, error=error))
    return ordered


def resolve_load_order(
    candidates: Iterable[PluginCandidate], core_api_version: Version
) -> Resolution:
    candidate_list = list(candidates)
    failures: list[ResolutionFailure] = []
    counts = Counter(candidate.key for candidate in candidate_list)
    usable: dict[str, PluginCandidate] = {}
    for candidate in candidate_list:
        if counts[candidate.key] > 1:
            error = PluginMessages.DUPLICATE_KEY.format(key=candidate.key)
        elif not candidate.manifest.core_api.allows(core_api_version):
            error = PluginMessages.INCOMPATIBLE_CORE_API.format(
                required=candidate.manifest.compatibility.core_api, provided=core_api_version
            )
        else:
            usable[candidate.key] = candidate
            continue
        failures.append(ResolutionFailure(key=candidate.key, root=candidate.root, error=error))
    _drop_unsatisfied(usable, failures)
    ordered = _topological_order(usable, failures)
    return Resolution(ordered=tuple(ordered), failures=tuple(failures))
