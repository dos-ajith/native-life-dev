"""add category slug

Revision ID: a1c7e5d9b3f2
Revises: fc3ab35b9d97
Create Date: 2026-10-16 12:00:00.000000

Existing categories are backfilled from their name. The first category with a
given slug keeps it; later ones (same name under another parent, or names with
no latin letters) get the first 8 characters of their id appended.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c7e5d9b3f2'
down_revision: Union[str, Sequence[str], None] = 'fc3ab35b9d97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categories', sa.Column('slug', sa.String(length=120), nullable=True))
    op.execute(
        """
        WITH base AS (
            SELECT id,
                   trim(both '-' from regexp_replace(lower(trim(name)), '[^a-z0-9]+', '-', 'g')) AS base_slug,
                   created_at
            FROM categories
        ),
        ranked AS (
            SELECT id, base_slug,
                   row_number() OVER (PARTITION BY base_slug ORDER BY created_at, id) AS position
            FROM base
        )
        UPDATE categories
        SET slug = CASE
            WHEN ranked.base_slug = '' THEN substr(categories.id::text, 1, 8)
            WHEN ranked.position = 1 THEN ranked.base_slug
            ELSE ranked.base_slug || '-' || substr(categories.id::text, 1, 8)
        END
        FROM ranked
        WHERE ranked.id = categories.id
        """
    )
    op.alter_column('categories', 'slug', nullable=False)
    op.create_unique_constraint('uq_categories_slug', 'categories', ['slug'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_categories_slug', 'categories', type_='unique')
    op.drop_column('categories', 'slug')
