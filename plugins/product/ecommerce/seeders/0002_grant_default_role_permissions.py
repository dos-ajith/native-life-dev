import tomllib
import uuid
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "plugin.toml"
DEFAULT_ROLE_SLUGS = ("business-service-provider", "native-admin")

PERMISSIONS = sa.table(
    "permissions",
    sa.column("id", sa.Uuid()),
    sa.column("name", sa.String()),
    sa.column("description", sa.String()),
)
ROLES = sa.table("roles", sa.column("id", sa.Uuid()), sa.column("slug", sa.String()))
ROLE_PERMISSIONS = sa.table(
    "role_has_permissions", sa.column("role_id", sa.Uuid()), sa.column("permission_id", sa.Uuid())
)


def _declared_permissions() -> dict[str, str]:
    manifest = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {
        name: declaration["description"] for name, declaration in manifest["permissions"].items()
    }


def seed(connection: Connection) -> None:
    declared = _declared_permissions()
    connection.execute(
        insert(PERMISSIONS)
        .values(
            [
                {"id": uuid.uuid4(), "name": name, "description": description}
                for name, description in declared.items()
            ]
        )
        .on_conflict_do_nothing(index_elements=["name"])
    )
    permission_ids = list(
        connection.execute(
            sa.select(PERMISSIONS.c.id).where(PERMISSIONS.c.name.in_(declared))
        ).scalars()
    )
    role_ids = list(
        connection.execute(
            sa.select(ROLES.c.id).where(ROLES.c.slug.in_(DEFAULT_ROLE_SLUGS))
        ).scalars()
    )
    rows = [
        {"role_id": role_id, "permission_id": permission_id}
        for permission_id in permission_ids
        for role_id in role_ids
    ]
    if rows:
        connection.execute(insert(ROLE_PERMISSIONS).values(rows).on_conflict_do_nothing())
