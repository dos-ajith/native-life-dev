"""add native admin to villages

Revision ID: d6f1b3a95e20
Revises: c5e8a19d3f72
Create Date: 2026-11-04 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd6f1b3a95e20'
down_revision: str | Sequence[str] | None = 'c5e8a19d3f72'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('gis_villages', sa.Column('native_admin_id', sa.UUID(), nullable=True))
    op.create_unique_constraint(
        'uq_gis_villages_native_admin_id', 'gis_villages', ['native_admin_id']
    )
    op.create_foreign_key(
        'fk_gis_villages_native_admin_id_users',
        'gis_villages',
        'users',
        ['native_admin_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_gis_villages_native_admin_id_users', 'gis_villages', type_='foreignkey')
    op.drop_constraint('uq_gis_villages_native_admin_id', 'gis_villages', type_='unique')
    op.drop_column('gis_villages', 'native_admin_id')
