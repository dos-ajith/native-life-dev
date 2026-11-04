import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, DateTime, MetaData, String, Table, func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from app.core.messages import PluginMessages
from app.plugins.discovery import PluginCandidate
from app.plugins.errors import PluginError

MIGRATIONS_DIRECTORY = "migrations"
SEEDERS_DIRECTORY = "seeders"
MIGRATION_ENTRYPOINT = "upgrade"
SEEDER_ENTRYPOINT = "seed"
REVISION_MAX_LENGTH = 100
SCRIPT_PATTERN = re.compile(r"^\d{4}_[a-z0-9_]+\.py$")
PACKAGE_MARKER = "__init__.py"


def migrations_table_name(key: str) -> str:
    return f"plg_{key}_migrations"


def _script_paths(root: Path, directory: str, missing_message: str) -> list[Path]:
    folder = root / directory
    if not folder.is_dir():
        raise PluginError(missing_message)
    paths = sorted(path for path in folder.iterdir() if path.is_file() and path.suffix == ".py")
    for path in paths:
        if path.name != PACKAGE_MARKER and not SCRIPT_PATTERN.match(path.name):
            raise PluginError(
                PluginMessages.INVALID_SCRIPT_FILENAME.format(path=f"{directory}/{path.name}")
            )
    return [path for path in paths if path.name != PACKAGE_MARKER]


def _load_entrypoint(path: Path, name: str) -> Callable[[Any], None]:
    namespace: dict[str, Any] = {"__name__": f"plugin_script_{path.stem}", "__file__": str(path)}
    exec(compile(path.read_bytes(), str(path), "exec"), namespace)
    entrypoint = namespace.get(name)
    if not callable(entrypoint):
        raise PluginError(
            PluginMessages.SCRIPT_ENTRYPOINT_MISSING.format(
                path=f"{path.parent.name}/{path.name}", name=name
            )
        )
    return cast(Callable[[Any], None], entrypoint)


def _migrations_table(key: str) -> Table:
    return Table(
        migrations_table_name(key),
        MetaData(),
        Column("revision", String(REVISION_MAX_LENGTH), primary_key=True),
        Column("applied_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    )


def validate_database_scripts(candidate: PluginCandidate) -> None:
    database = candidate.manifest.database
    if database.migrations:
        _script_paths(
            candidate.root, MIGRATIONS_DIRECTORY, PluginMessages.MIGRATIONS_DIRECTORY_MISSING
        )
    if database.seeders:
        _script_paths(candidate.root, SEEDERS_DIRECTORY, PluginMessages.SEEDERS_DIRECTORY_MISSING)


def run_migrations(connection: Connection, candidate: PluginCandidate) -> list[str]:
    paths = _script_paths(
        candidate.root, MIGRATIONS_DIRECTORY, PluginMessages.MIGRATIONS_DIRECTORY_MISSING
    )
    table = _migrations_table(candidate.key)
    table.create(connection, checkfirst=True)
    applied: set[str] = set(connection.execute(select(table.c.revision)).scalars())
    on_disk = {path.stem for path in paths}
    missing = sorted(applied - on_disk)
    if missing:
        raise PluginError(PluginMessages.UNKNOWN_APPLIED_MIGRATION.format(revision=missing[0]))
    operations = Operations(MigrationContext.configure(connection))
    newly_applied: list[str] = []
    for path in paths:
        if path.stem in applied:
            continue
        upgrade = _load_entrypoint(path, MIGRATION_ENTRYPOINT)
        try:
            upgrade(operations)
            connection.execute(table.insert().values(revision=path.stem))
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                PluginMessages.MIGRATION_FAILED.format(name=path.stem, error=type(exc).__name__)
            ) from exc
        newly_applied.append(path.stem)
    return newly_applied


def run_seeders(connection: Connection, candidate: PluginCandidate) -> list[str]:
    paths = _script_paths(
        candidate.root, SEEDERS_DIRECTORY, PluginMessages.SEEDERS_DIRECTORY_MISSING
    )
    for path in paths:
        seed = _load_entrypoint(path, SEEDER_ENTRYPOINT)
        try:
            seed(connection)
        except PluginError:
            raise
        except Exception as exc:
            raise PluginError(
                PluginMessages.SEEDER_FAILED.format(name=path.stem, error=type(exc).__name__)
            ) from exc
    return [path.stem for path in paths]


def run_database_scripts(db: Session, candidate: PluginCandidate) -> None:
    database = candidate.manifest.database
    if not database.migrations and not database.seeders:
        return
    connection = db.connection()
    if database.migrations:
        run_migrations(connection, candidate)
    if database.seeders:
        run_seeders(connection, candidate)
