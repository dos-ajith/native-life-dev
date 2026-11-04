"""add post audience and reaction type

Revision ID: 4dd605bf5e34
Revises: 43b997b1e15c
Create Date: 2026-10-12 14:28:21.504151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4dd605bf5e34'
down_revision: Union[str, Sequence[str], None] = '43b997b1e15c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

post_audience = postgresql.ENUM('everyone', 'adults_only', name='post_audience', create_type=False)
post_reaction_type = postgresql.ENUM(
    'like', 'love', 'laugh', 'wow', name='post_reaction_type', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    post_audience.create(op.get_bind(), checkfirst=True)
    post_reaction_type.create(op.get_bind(), checkfirst=True)
    op.add_column('posts', sa.Column('audience', post_audience, server_default='everyone', nullable=False))
    op.add_column('post_likes', sa.Column('reaction_type', post_reaction_type, server_default='like', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('post_likes', 'reaction_type')
    op.drop_column('posts', 'audience')
    post_reaction_type.drop(op.get_bind(), checkfirst=True)
    post_audience.drop(op.get_bind(), checkfirst=True)
