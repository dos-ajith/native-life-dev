"""add account role selection and verification

Revision ID: ad4743bffa50
Revises: a3c7e9b1d204
Create Date: 2026-10-09 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad4743bffa50'
down_revision: Union[str, Sequence[str], None] = 'a3c7e9b1d204'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERIFIED_ACCOUNT_ROLE_SLUGS = "('promoter', 'club', 'community', 'business-profile', 'service-provider')"
ROLE_DISPLAY_NAMES = (
    ('public-user', 'Public User', 'Individual User'),
    ('business-profile', 'Business Profile', 'Business'),
)
PENDING_INDEX = 'uq_role_upgrade_requests_pending_user_role'


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE role_upgrade_request_status ADD VALUE IF NOT EXISTS 'cancelled'")

    op.add_column('users', sa.Column('account_role_selected_at', sa.DateTime(), nullable=True))
    op.add_column(
        'user_has_roles',
        sa.Column('assigned_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    )
    op.add_column('user_has_roles', sa.Column('verified_at', sa.DateTime(), nullable=True))

    op.execute(
        "UPDATE user_has_roles uhr SET assigned_at = u.created_at "
        "FROM users u WHERE u.id = uhr.user_id"
    )
    op.execute(
        "UPDATE user_has_roles uhr "
        "SET assigned_at = approved.reviewed_at, verified_at = approved.reviewed_at "
        "FROM ("
        "  SELECT DISTINCT ON (r.user_id, r.requested_role_id) "
        "    r.user_id, r.requested_role_id, r.reviewed_at "
        "  FROM role_upgrade_requests r "
        "  WHERE r.status = 'approved' AND r.reviewed_at IS NOT NULL "
        "  ORDER BY r.user_id, r.requested_role_id, r.reviewed_at DESC"
        ") approved, roles "
        "WHERE approved.user_id = uhr.user_id "
        "AND approved.requested_role_id = uhr.role_id "
        "AND roles.id = uhr.role_id "
        f"AND roles.slug IN {VERIFIED_ACCOUNT_ROLE_SLUGS}"
    )
    op.execute(
        "UPDATE role_upgrade_requests r SET status = 'cancelled', updated_at = now() "
        "WHERE r.status = 'pending' AND NOT EXISTS ("
        "  SELECT 1 FROM user_has_roles uhr "
        "  WHERE uhr.user_id = r.user_id AND uhr.role_id = r.requested_role_id"
        ")"
    )
    for slug, old_name, new_name in ROLE_DISPLAY_NAMES:
        op.execute(
            sa.text(
                "UPDATE roles SET name = :new_name, updated_at = now() "
                "WHERE slug = :slug AND name = :old_name "
                "AND NOT EXISTS (SELECT 1 FROM roles WHERE name = :new_name)"
            ).bindparams(slug=slug, old_name=old_name, new_name=new_name)
        )


def downgrade() -> None:
    """Downgrade schema."""
    for slug, old_name, new_name in ROLE_DISPLAY_NAMES:
        op.execute(
            sa.text(
                "UPDATE roles SET name = :old_name, updated_at = now() "
                "WHERE slug = :slug AND name = :new_name "
                "AND NOT EXISTS (SELECT 1 FROM roles WHERE name = :old_name)"
            ).bindparams(slug=slug, old_name=old_name, new_name=new_name)
        )

    op.drop_column('user_has_roles', 'verified_at')
    op.drop_column('user_has_roles', 'assigned_at')
    op.drop_column('users', 'account_role_selected_at')

    op.drop_index(PENDING_INDEX, table_name='role_upgrade_requests')
    op.execute("UPDATE role_upgrade_requests SET status = 'rejected' WHERE status = 'cancelled'")
    op.execute("ALTER TYPE role_upgrade_request_status RENAME TO role_upgrade_request_status_old")
    op.execute("CREATE TYPE role_upgrade_request_status AS ENUM ('pending', 'approved', 'rejected')")
    op.execute(
        "ALTER TABLE role_upgrade_requests ALTER COLUMN status TYPE role_upgrade_request_status "
        "USING status::text::role_upgrade_request_status"
    )
    op.execute("DROP TYPE role_upgrade_request_status_old")
    op.create_index(
        PENDING_INDEX,
        'role_upgrade_requests',
        ['user_id', 'requested_role_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )
