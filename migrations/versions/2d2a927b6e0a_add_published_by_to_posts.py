"""add published_by to posts

Revision ID: 2d2a927b6e0a
Revises: edfc0e7b0bc4
Create Date: 2026-09-21 13:26:02.172107

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2d2a927b6e0a'
down_revision: Union[str, Sequence[str], None] = 'edfc0e7b0bc4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('published_by', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('posts_published_by_fkey'), 'posts', 'users', ['published_by'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_posts_published_by', 'posts', ['published_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_published_by', table_name='posts')
    op.drop_constraint(op.f('posts_published_by_fkey'), 'posts', type_='foreignkey')
    op.drop_column('posts', 'published_by')
