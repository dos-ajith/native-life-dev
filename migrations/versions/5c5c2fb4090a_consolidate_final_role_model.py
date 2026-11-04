"""consolidate final role model

Revision ID: 5c5c2fb4090a
Revises: ad4743bffa50
Create Date: 2026-10-10 10:00:00.000000

"""
from typing import Sequence, Union
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine import Connection


# revision identifiers, used by Alembic.
revision: str = '5c5c2fb4090a'
down_revision: Union[str, Sequence[str], None] = 'ad4743bffa50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REQUESTED_ROLE_FK = 'role_upgrade_requests_requested_role_id_fkey'
INDIVIDUAL_USER = ('individual-user', 'Individual User')
CONSOLIDATIONS = (
    (INDIVIDUAL_USER, ('public-user',)),
    (('club-community', 'Club / Community'), ('club', 'community')),
    (
        ('business-service-provider', 'Business / Service Provider'),
        ('business-profile', 'service-provider'),
    ),
)
RETIRED_ROLE_SLUGS = ('public-authority', 'delivery-team-member')
ADMIN_ROLE_SLUGS = ('super-admin', 'native-admin')
DOWNGRADE_SLUGS = (
    ('individual-user', 'public-user', 'Individual User'),
    ('business-service-provider', 'business-profile', 'Business'),
    ('club-community', 'club', 'Club'),
)


def _role_id(bind: Connection, slug: str) -> UUID | None:
    return bind.execute(
        sa.text("SELECT id FROM roles WHERE slug = :slug"), {"slug": slug}
    ).scalar_one_or_none()


def _merge(bind: Connection, source_id: UUID, target_id: UUID) -> None:
    params = {"source": source_id, "target": target_id}
    bind.execute(
        sa.text(
            "UPDATE role_upgrade_requests s SET status = 'cancelled', updated_at = now() "
            "WHERE s.requested_role_id = :source AND s.status = 'pending' AND EXISTS ("
            "  SELECT 1 FROM role_upgrade_requests t WHERE t.user_id = s.user_id "
            "  AND t.requested_role_id = :target AND t.status = 'pending')"
        ),
        params,
    )
    bind.execute(
        sa.text(
            "UPDATE role_upgrade_requests SET requested_role_id = :target "
            "WHERE requested_role_id = :source"
        ),
        params,
    )
    bind.execute(
        sa.text(
            "INSERT INTO user_has_roles (user_id, role_id, assigned_at, verified_at) "
            "SELECT user_id, :target, assigned_at, verified_at FROM user_has_roles "
            "WHERE role_id = :source ON CONFLICT (user_id, role_id) DO NOTHING"
        ),
        params,
    )
    bind.execute(sa.text("DELETE FROM roles WHERE id = :source"), params)


def _consolidate(bind: Connection, target: tuple[str, str], sources: tuple[str, ...]) -> None:
    target_slug, target_name = target
    target_id = _role_id(bind, target_slug)
    for source_slug in sources:
        source_id = _role_id(bind, source_slug)
        if source_id is None:
            continue
        if target_id is None:
            bind.execute(
                sa.text("UPDATE roles SET slug = :slug, updated_at = now() WHERE id = :id"),
                {"slug": target_slug, "id": source_id},
            )
            target_id = source_id
        else:
            _merge(bind, source_id, target_id)
    if target_id is not None:
        bind.execute(
            sa.text(
                "UPDATE roles SET name = :name, updated_at = now() "
                "WHERE id = :id AND name <> :name "
                "AND NOT EXISTS (SELECT 1 FROM roles WHERE name = :name)"
            ),
            {"name": target_name, "id": target_id},
        )


def _retire_legacy_roles(bind: Connection) -> None:
    legacy_ids = [
        role_id
        for role_id in (_role_id(bind, slug) for slug in RETIRED_ROLE_SLUGS)
        if role_id is not None
    ]
    if not legacy_ids:
        return
    legacy = sa.bindparam('legacy', expanding=True)
    admins = sa.bindparam('admins', expanding=True)
    base_id = _role_id(bind, INDIVIDUAL_USER[0])
    if base_id is None:
        base_id = bind.execute(
            sa.text(
                "INSERT INTO roles (id, name, slug) VALUES (gen_random_uuid(), :name, :slug) "
                "RETURNING id"
            ),
            {"name": INDIVIDUAL_USER[1], "slug": INDIVIDUAL_USER[0]},
        ).scalar_one()
    bind.execute(
        sa.text(
            "INSERT INTO user_has_roles (user_id, role_id, assigned_at) "
            "SELECT DISTINCT ON (uhr.user_id) uhr.user_id, :base, uhr.assigned_at "
            "FROM user_has_roles uhr "
            "WHERE uhr.role_id IN :legacy AND NOT EXISTS ("
            "  SELECT 1 FROM user_has_roles held JOIN roles r ON r.id = held.role_id "
            "  WHERE held.user_id = uhr.user_id AND r.slug IN :admins) "
            "ORDER BY uhr.user_id, uhr.assigned_at "
            "ON CONFLICT (user_id, role_id) DO NOTHING"
        ).bindparams(legacy, admins),
        {"base": base_id, "legacy": legacy_ids, "admins": list(ADMIN_ROLE_SLUGS)},
    )
    bind.execute(
        sa.text(
            "UPDATE role_upgrade_requests SET status = 'cancelled', updated_at = now() "
            "WHERE requested_role_id IN :legacy AND status = 'pending'"
        ).bindparams(legacy),
        {"legacy": legacy_ids},
    )
    bind.execute(
        sa.text("DELETE FROM roles WHERE id IN :legacy").bindparams(legacy),
        {"legacy": legacy_ids},
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint(REQUESTED_ROLE_FK, 'role_upgrade_requests', type_='foreignkey')
    op.alter_column('role_upgrade_requests', 'requested_role_id', nullable=True)
    op.create_foreign_key(
        REQUESTED_ROLE_FK,
        'role_upgrade_requests',
        'roles',
        ['requested_role_id'],
        ['id'],
        ondelete='SET NULL',
    )

    bind = op.get_bind()
    for target, sources in CONSOLIDATIONS:
        _consolidate(bind, target, sources)
    _retire_legacy_roles(bind)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    orphaned = bind.execute(
        sa.text("SELECT count(*) FROM role_upgrade_requests WHERE requested_role_id IS NULL")
    ).scalar_one()
    if orphaned:
        raise RuntimeError(
            f"Refusing to downgrade: {orphaned} role upgrade request(s) reference a retired role"
        )

    for slug, old_slug, old_name in DOWNGRADE_SLUGS:
        if _role_id(bind, old_slug) is not None:
            continue
        bind.execute(
            sa.text(
                "UPDATE roles SET slug = :old_slug, name = :old_name, updated_at = now() "
                "WHERE slug = :slug AND NOT EXISTS ("
                "  SELECT 1 FROM roles other WHERE other.name = :old_name AND other.slug <> :slug)"
            ),
            {"slug": slug, "old_slug": old_slug, "old_name": old_name},
        )

    op.drop_constraint(REQUESTED_ROLE_FK, 'role_upgrade_requests', type_='foreignkey')
    op.alter_column('role_upgrade_requests', 'requested_role_id', nullable=False)
    op.create_foreign_key(
        REQUESTED_ROLE_FK,
        'role_upgrade_requests',
        'roles',
        ['requested_role_id'],
        ['id'],
        ondelete='CASCADE',
    )
