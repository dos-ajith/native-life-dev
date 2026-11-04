import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.messages import PluginMessages
from app.plugins.boundaries import find_boundary_violations
from app.plugins.discovery import discover_plugins
from app.plugins.errors import PluginError
from app.plugins.packaging import install_archive, package_plugin
from app.plugins.resolution import resolve_load_order
from app.plugins.smoke import SMOKE_COMMAND, run_smoke_load, smoke_load_in_process
from app.plugins.versioning import CORE_API_VERSION
from app.services.plugin_installation_service import ApplyOutcome, PluginInstallationService

EXIT_OK = 0
EXIT_FAILED = 1
DEFAULT_PACKAGE_DIRECTORY = "plugin_packages"


def _plugins_dir() -> Path:
    return Path(get_settings().plugins_dir)


def _validate() -> int:
    discovery = discover_plugins(_plugins_dir())
    resolution = resolve_load_order(discovery.candidates, CORE_API_VERSION)
    has_failures = bool(resolution.failures or discovery.failures)
    for candidate in resolution.ordered:
        violations = find_boundary_violations(candidate.root)
        if violations:
            has_failures = True
            print(f"failed  {candidate.key}  ({candidate.root}): {'; '.join(violations)}")
        else:
            print(f"ok      {candidate.key} {candidate.manifest.version}  ({candidate.root})")
    for failure in resolution.failures:
        print(f"failed  {failure.key}  ({failure.root}): {failure.error}")
    for discovery_failure in discovery.failures:
        print(f"failed  ({discovery_failure.root}): {discovery_failure.error}")
    return EXIT_FAILED if has_failures else EXIT_OK


def _apply(keys: Sequence[str]) -> int:
    discovery = discover_plugins(_plugins_dir())
    unknown = sorted(set(keys) - {candidate.key for candidate in discovery.candidates})
    if unknown:
        print(PluginMessages.UNKNOWN_PLUGIN_KEYS.format(keys=", ".join(unknown)), file=sys.stderr)
        return EXIT_FAILED
    with SessionLocal() as db:
        results = PluginInstallationService(db, smoke_loader=run_smoke_load).apply(
            discovery, set(keys)
        )
    for result in results:
        label = result.key or result.path
        detail = f": {result.message}" if result.message else ""
        print(f"{result.outcome.value:<10}{label} {result.version or ''}{detail}")
    if any(result.outcome != ApplyOutcome.UNCHANGED for result in results):
        print("Restart the application to load new or upgraded plugin code.")
    failed = any(result.outcome == ApplyOutcome.FAILED for result in results)
    return EXIT_FAILED if failed else EXIT_OK


def _package(key: str, output_dir: str) -> int:
    try:
        result = package_plugin(_plugins_dir(), key, Path(output_dir))
    except PluginError as exc:
        print(exc.message, file=sys.stderr)
        return EXIT_FAILED
    print(
        PluginMessages.PACKAGE_CREATED.format(
            key=result.key, version=result.version, path=result.path
        )
    )
    return EXIT_OK


def _install(archive: str, replace: bool) -> int:
    try:
        result = install_archive(_plugins_dir(), Path(archive), replace)
    except PluginError as exc:
        print(exc.message, file=sys.stderr)
        return EXIT_FAILED
    print(
        PluginMessages.PACKAGE_EXTRACTED.format(
            key=result.key, version=result.version, path=result.path
        )
    )
    print(
        f"Next: python -m app.plugins.cli apply --key {result.key}, then restart the application."
    )
    return EXIT_OK


def _smoke(path: str) -> int:
    try:
        smoke_load_in_process(Path(path))
    except PluginError as exc:
        print(exc.message, file=sys.stderr)
        return EXIT_FAILED
    return EXIT_OK


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.plugins.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate plugin manifests and dependencies (no database)")
    apply = commands.add_parser("apply", help="Register trusted local plugins in the database")
    apply.add_argument("--key", action="append", default=[], help="Apply only this plugin key")
    package = commands.add_parser("package", help="Build a ZIP package of one local plugin")
    package.add_argument("--key", required=True, help="Key of the plugin to package")
    package.add_argument("--output-dir", default=DEFAULT_PACKAGE_DIRECTORY)
    install = commands.add_parser(
        "install", help="Extract a plugin ZIP package into the plugins directory (then run apply)"
    )
    install.add_argument("archive")
    install.add_argument("--replace", action="store_true", help="Overwrite an existing install")
    smoke = commands.add_parser(SMOKE_COMMAND, help="Internal: load one plugin in this process")
    smoke.add_argument("path")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "validate":
        return _validate()
    if args.command == "apply":
        return _apply(args.key)
    if args.command == "package":
        return _package(args.key, args.output_dir)
    if args.command == "install":
        return _install(args.archive, args.replace)
    return _smoke(args.path)


if __name__ == "__main__":
    raise SystemExit(main())
