import os
import shutil
import stat
import tempfile
import zipfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.messages import PluginMessages
from app.plugins.boundaries import find_boundary_violations
from app.plugins.database_scripts import validate_database_scripts
from app.plugins.discovery import (
    PluginCandidate,
    discover_plugins,
    load_candidate,
    plugin_content_files,
    plugin_content_sha256,
)
from app.plugins.errors import PluginConflictError, PluginError
from app.plugins.layout import GENERATED_FILE_NAMES, GENERATED_FILE_SUFFIXES, UNVERIFIED_DIRECTORIES
from app.plugins.manifest import MANIFEST_FILENAME
from app.plugins.versioning import CORE_API_VERSION

CHECKSUM_MEMBER = "CONTENT_SHA256"
ARCHIVE_SUFFIX = ".zip"
FIXED_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
FILE_MODE = 0o644
MAX_ARCHIVE_FILES = 2000
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
PACKAGE_INIT_FILENAME = "__init__.py"
STAGING_PREFIX = ".plugin-import-"
PACKAGES_DIRECTORY = "plugin_packages"
MAX_REPORTED_VIOLATIONS = 5


@dataclass(frozen=True)
class PackageResult:
    key: str
    version: str
    path: Path


@dataclass(frozen=True)
class StagedPackage:
    path: Path
    workspace: Path
    candidate: PluginCandidate


@dataclass(frozen=True)
class InstallResult:
    key: str
    version: str
    path: Path


def archive_name(candidate: PluginCandidate) -> str:
    return f"{candidate.key}-{candidate.manifest.version}{ARCHIVE_SUFFIX}"


def _entry(name: str, data: bytes) -> tuple[zipfile.ZipInfo, bytes]:
    info = zipfile.ZipInfo(name, date_time=FIXED_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | FILE_MODE) << 16
    return info, data


def package_plugin(plugins_dir: Path, key: str, output_dir: Path) -> PackageResult:
    candidate = next(
        (item for item in discover_plugins(plugins_dir).candidates if item.key == key), None
    )
    if candidate is None:
        raise PluginError(PluginMessages.PACKAGE_UNKNOWN_KEY.format(key=key))
    violations = find_boundary_violations(candidate.root)
    if violations:
        raise PluginError("; ".join(violations[:MAX_REPORTED_VIOLATIONS]))
    output_dir = output_dir / candidate.key
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / archive_name(candidate)
    entries = [
        _entry(path.relative_to(candidate.root).as_posix(), path.read_bytes())
        for path in plugin_content_files(candidate.root)
    ]
    entries.append(_entry(CHECKSUM_MEMBER, candidate.content_sha256.encode()))
    with zipfile.ZipFile(destination, "w") as archive:
        for info, data in entries:
            archive.writestr(info, data)
    return PackageResult(
        key=candidate.key, version=str(candidate.manifest.version), path=destination
    )


def _ensure_safe_member(info: zipfile.ZipInfo) -> PurePosixPath:
    path = PurePosixPath(info.filename)
    is_unsafe = (
        info.filename.startswith("/")
        or "\\" in info.filename
        or ".." in path.parts
        or stat.S_ISLNK(info.external_attr >> 16)
        or not info.filename
        or any(part in UNVERIFIED_DIRECTORIES for part in path.parts)
        or path.name in GENERATED_FILE_NAMES
        or path.suffix in GENERATED_FILE_SUFFIXES
    )
    if is_unsafe:
        raise PluginError(PluginMessages.PACKAGE_UNSAFE_MEMBER.format(name=info.filename))
    return path


def _extract(archive: zipfile.ZipFile, target: Path) -> str:
    members = [info for info in archive.infolist() if not info.is_dir()]
    if (
        len(members) > MAX_ARCHIVE_FILES
        or sum(info.file_size for info in members) > MAX_ARCHIVE_BYTES
    ):
        raise PluginError(PluginMessages.PACKAGE_TOO_LARGE)
    checksum: str | None = None
    resolved_target = target.resolve()
    for info in members:
        path = _ensure_safe_member(info)
        data = archive.read(info)
        if str(path) == CHECKSUM_MEMBER:
            checksum = data.decode("utf-8", errors="replace").strip()
            continue
        destination = (target / Path(*path.parts)).resolve()
        if not destination.is_relative_to(resolved_target):
            raise PluginError(PluginMessages.PACKAGE_UNSAFE_MEMBER.format(name=info.filename))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    if checksum is None:
        raise PluginError(PluginMessages.PACKAGE_CHECKSUM_MISSING.format(name=CHECKSUM_MEMBER))
    return checksum


def _ensure_required_files(extracted: Path, candidate: PluginCandidate) -> None:
    if not (extracted / PACKAGE_INIT_FILENAME).is_file():
        raise PluginError(
            PluginMessages.PACKAGE_REQUIRED_FILE_MISSING.format(path=PACKAGE_INIT_FILENAME)
        )
    module_path = candidate.manifest.entrypoint.module.replace(".", "/")
    if not any(
        (extracted / f"{module_path}{suffix}").is_file() for suffix in (".py", "/__init__.py")
    ):
        raise PluginError(
            PluginMessages.PACKAGE_REQUIRED_FILE_MISSING.format(path=f"{module_path}.py")
        )
    validate_database_scripts(candidate)


def _verified_candidate(extracted: Path, expected_sha256: str) -> PluginCandidate:
    if not (extracted / MANIFEST_FILENAME).is_file():
        raise PluginError(PluginMessages.PACKAGE_MANIFEST_MISSING)
    if plugin_content_sha256(extracted) != expected_sha256:
        raise PluginError(PluginMessages.PACKAGE_CHECKSUM_MISMATCH.format(name=CHECKSUM_MEMBER))
    candidate = load_candidate(extracted)
    _ensure_required_files(extracted, candidate)
    if not candidate.manifest.core_api.allows(CORE_API_VERSION):
        raise PluginError(
            PluginMessages.INCOMPATIBLE_CORE_API.format(
                required=candidate.manifest.compatibility.core_api, provided=CORE_API_VERSION
            )
        )
    violations = find_boundary_violations(extracted)
    if violations:
        raise PluginError("; ".join(violations[:MAX_REPORTED_VIOLATIONS]))
    return candidate


def _ensure_key_not_elsewhere(plugins_dir: Path, key: str, destination: Path) -> None:
    for existing in discover_plugins(plugins_dir).candidates:
        if existing.key == key and existing.root.resolve() != destination.resolve():
            raise PluginConflictError(
                PluginMessages.PACKAGE_KEY_ELSEWHERE.format(key=key, path=existing.root)
            )


def _is_free(destination: Path) -> bool:
    return not destination.exists() or (destination.is_dir() and not any(destination.iterdir()))


@contextmanager
def staged_archive(plugins_dir: Path, archive_path: Path) -> Iterator[StagedPackage]:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=STAGING_PREFIX, dir=plugins_dir.parent) as workspace:
        extracted = Path(workspace) / "plugin"
        extracted.mkdir()
        try:
            with zipfile.ZipFile(archive_path) as archive:
                expected = _extract(archive, extracted)
        except (zipfile.BadZipFile, OSError) as exc:
            raise PluginError(PluginMessages.PACKAGE_UNREADABLE.format(error=exc)) from exc
        candidate = _verified_candidate(extracted, expected)
        yield StagedPackage(path=extracted, workspace=Path(workspace), candidate=candidate)


def install_archive(
    plugins_dir: Path,
    archive_path: Path,
    replace: bool,
    is_registered: Callable[[str], bool] | None = None,
) -> InstallResult:
    with staged_archive(plugins_dir, archive_path) as staged:
        candidate = staged.candidate
        if is_registered is not None and is_registered(candidate.key):
            raise PluginConflictError(
                PluginMessages.PACKAGE_ALREADY_REGISTERED.format(key=candidate.key)
            )
        destination = plugins_dir / candidate.manifest.plugin.business_type / candidate.key
        _ensure_key_not_elsewhere(plugins_dir, candidate.key, destination)
        if not _is_free(destination):
            if not replace:
                raise PluginConflictError(
                    PluginMessages.PACKAGE_ALREADY_INSTALLED.format(
                        key=candidate.key, path=destination
                    )
                )
            shutil.rmtree(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_dir():
            destination.rmdir()
        try:
            os.rename(staged.path, destination)
        except OSError as exc:
            if not _is_free(destination):
                raise PluginConflictError(
                    PluginMessages.PACKAGE_ALREADY_INSTALLED.format(
                        key=candidate.key, path=destination
                    )
                ) from exc
            shutil.copytree(staged.path, destination)
    return InstallResult(
        key=candidate.key, version=str(candidate.manifest.version), path=destination
    )
