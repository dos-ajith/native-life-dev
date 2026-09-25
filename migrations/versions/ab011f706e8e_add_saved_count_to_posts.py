"""add saved_count to posts

Revision ID: ab011f706e8e
Revises: 07552e05b4b3
Create Date: 2026-09-25 15:00:07.060777

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ab011f706e8e'
down_revision: Union[str, Sequence[str], None] = '07552e05b4b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('posts', sa.Column('saved_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.execute(
        """
        UPDATE posts
        SET saved_count = counts.total
        FROM (SELECT post_id, count(*) AS total FROM saved_posts GROUP BY post_id) AS counts
        WHERE posts.id = counts.post_id
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('posts', 'saved_count')
