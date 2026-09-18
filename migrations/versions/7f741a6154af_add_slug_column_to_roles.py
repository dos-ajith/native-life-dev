"""add slug column to roles

Revision ID: 7f741a6154af
Revises: f9dd1dda65ce
Create Date: 2026-09-18 12:33:11.482987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7f741a6154af'
down_revision: Union[str, Sequence[str], None] = 'f9dd1dda65ce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('roles', sa.Column('slug', sa.String(length=120), nullable=True))
    op.execute(
        "UPDATE roles SET slug = trim(both '-' from lower(regexp_replace(name, '[^a-zA-Z0-9]+', '-', 'g')))"
    )
    op.alter_column('roles', 'slug', nullable=False)
    op.create_unique_constraint('uq_roles_slug', 'roles', ['slug'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_roles_slug', 'roles', type_='unique')
    op.drop_column('roles', 'slug')
