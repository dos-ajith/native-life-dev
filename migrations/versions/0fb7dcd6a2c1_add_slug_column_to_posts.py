"""add slug column to posts

Revision ID: 0fb7dcd6a2c1
Revises: 589a050bf52a
Create Date: 2026-09-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fb7dcd6a2c1'
down_revision: Union[str, Sequence[str], None] = '589a050bf52a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('slug', sa.String(length=280), nullable=True))
    op.execute(
        """
        UPDATE posts
        SET slug = CASE
            WHEN trim(both '-' from lower(regexp_replace(coalesce(title, ''), '[^a-zA-Z0-9]+', '-', 'g'))) = ''
                THEN substr(replace(id::text, '-', ''), 1, 8)
            ELSE trim(both '-' from lower(regexp_replace(title, '[^a-zA-Z0-9]+', '-', 'g')))
                 || '-' || substr(replace(id::text, '-', ''), 1, 8)
        END
        """
    )
    op.alter_column('posts', 'slug', nullable=False)
    op.create_unique_constraint('uq_posts_slug', 'posts', ['slug'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('uq_posts_slug', 'posts', type_='unique')
    op.drop_column('posts', 'slug')
