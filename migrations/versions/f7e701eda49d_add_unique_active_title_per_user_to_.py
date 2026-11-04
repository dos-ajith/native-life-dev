"""add unique active title per user to posts

Revision ID: f7e701eda49d
Revises: ab011f706e8e
Create Date: 2026-09-25 15:35:17.524413

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7e701eda49d'
down_revision: Union[str, Sequence[str], None] = 'ab011f706e8e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_posts_user_id_title_active',
        'posts',
        ['user_id', 'title'],
        unique=True,
        postgresql_where=sa.text('deleted_at IS NULL AND title IS NOT NULL'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_user_id_title_active', table_name='posts')
