"""add post visibility

Revision ID: f9c6e4a1b8d3
Revises: e8b5d3f0a7c2
Create Date: 2026-10-15 13:00:00.000000

Existing community posts become private so they keep their current behaviour
of staying inside the community; every other post is public.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9c6e4a1b8d3'
down_revision: Union[str, Sequence[str], None] = 'e8b5d3f0a7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    visibility = sa.Enum('public', 'private', name='post_visibility')
    visibility.create(op.get_bind(), checkfirst=True)
    op.add_column('posts', sa.Column('visibility', sa.Enum('public', 'private', name='post_visibility', create_type=False), server_default='public', nullable=False))
    op.execute("UPDATE posts SET visibility = 'private' WHERE community_id IS NOT NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('posts', 'visibility')
    op.execute("DROP TYPE post_visibility")
