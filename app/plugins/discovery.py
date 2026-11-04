import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from app.core.messages import PluginMessages
from app.plugins.errors import PluginError
from app.plugins.layout import GENERATED_FILE_NAMES, GENERATED_FILE_SUFFIXES, UNVERIFIED_DIRECTORIES
from app.plugins.manifest import MANIFEST_FILENAME, PluginManifest, load_manifest


@dataclass(frozen=True)
class PluginCandidate:
    manifest: PluginManifest
    root: Path
    content_sha256: str

    @property
    def key(self) -> str:
        return self.manifest.key


@dataclass(frozen=True)
class DiscoveryFailure:
    root: Path
    error: str


@dataclass(frozen=True)
class DiscoveryResult:
    candidates: tuple[PluginCandidate, ...]
    failures: tuple[DiscoveryFailure, ...]


def _is_content_file(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return (
        path.is_file()
        and path.suffix not in GENERATED_FILE_SUFFIXES
        and path.name not in GENERATED_FILE_NAMES
        and not any(part in UNVERIFIED_DIRECTORIES for part in relative_parts)
    )


def plugin_content_files(root: Path) -> list[Path]:
    return sorted(
        (path for path in root.rglob("*") if _is_content_file(path, root)),
        key=lambda path: path.relative_to(root).as_posix(),
    )


def plugin_content_sha256(root: Path) -> str:
    digest = hashlib.sha256()
    for path in plugin_content_files(root):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _unverifiable_entry(path: Path, root: Path) -> str | None:
    relative = path.relative_to(root).as_posix() if path != root else path.name
    if path.is_symlink():
        return PluginMessages.SYMLINK_FORBIDDEN.format(path=relative)
    if path.is_file() and path.suffix in GENERATED_FILE_SUFFIXES:
        return PluginMessages.STRAY_BYTECODE.format(path=relative)
    return None


def _ensure_verifiable_contents(root: Path) -> None:
    candidates = [root]
    for directory, subdirectories, files in os.walk(root):
        current = Path(directory)
        subdirectories.sort()
        candidates.extend(current / name for name in subdirectories)
        candidates.extend(current / name for name in sorted(files))
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in UNVERIFIED_DIRECTORIES and not (current / name).is_symlink()
        ]
    for path in candidates:
        error = _unverifiable_entry(path, root)
        if error is not None:
            raise PluginError(error)


def _ensure_ui_entries_exist(manifest: PluginManifest, root: Path) -> None:
    resolved_root = root.resolve()
    for section, bundle in manifest.ui_bundles.items():
        entry = (root / bundle.path / bundle.entry).resolve()
        if not entry.is_relative_to(resolved_root) or not entry.is_file():
            raise PluginError(
                PluginMessages.UI_ENTRY_MISSING.format(
                    section=section, entry=f"{bundle.path}/{bundle.entry}"
                )
            )


def load_candidate(root: Path) -> PluginCandidate:
    _ensure_verifiable_contents(root)
    manifest = load_manifest(root / MANIFEST_FILENAME)
    _ensure_ui_entries_exist(manifest, root)
    return PluginCandidate(manifest=manifest, root=root, content_sha256=plugin_content_sha256(root))


def _manifest_paths(plugins_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in plugins_dir.rglob(MANIFEST_FILENAME)
        if not any(part in UNVERIFIED_DIRECTORIES for part in path.relative_to(plugins_dir).parts)
    )


def _enclosing_root(root: Path, roots: set[Path]) -> Path | None:
    return next((parent for parent in root.parents if parent in roots), None)


def discover_plugins(plugins_dir: Path) -> DiscoveryResult:
    if not plugins_dir.is_dir():
        return DiscoveryResult(candidates=(), failures=())
    candidates: list[PluginCandidate] = []
    failures: list[DiscoveryFailure] = []
    roots = [manifest_path.parent for manifest_path in _manifest_paths(plugins_dir)]
    for root in roots:
        enclosing = _enclosing_root(root, set(roots))
        if enclosing is not None:
            failures.append(
                DiscoveryFailure(
                    root=root, error=PluginMessages.NESTED_PLUGIN_ROOT.format(parent=enclosing)
                )
            )
            continue
        try:
            candidates.append(load_candidate(root))
        except PluginError as exc:
            failures.append(DiscoveryFailure(root=root, error=exc.message))
    return DiscoveryResult(candidates=tuple(candidates), failures=tuple(failures))
