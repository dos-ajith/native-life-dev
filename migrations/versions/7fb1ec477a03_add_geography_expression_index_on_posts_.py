"""add geography expression index on posts location for nearby search

Revision ID: 7fb1ec477a03
Revises: 3ccf1dfde574
Create Date: 2026-09-22 21:13:55.866934

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7fb1ec477a03'
down_revision: Union[str, Sequence[str], None] = '3ccf1dfde574'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        'ix_posts_location_geography',
        'posts',
        [sa.text('(location::geography)')],
        unique=False,
        postgresql_using='gist',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_posts_location_geography', table_name='posts', postgresql_using='gist')
