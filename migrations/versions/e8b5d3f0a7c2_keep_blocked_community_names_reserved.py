"""keep blocked community names reserved

Revision ID: e8b5d3f0a7c2
Revises: d7a4c2e9b6f1
Create Date: 2026-10-15 12:30:00.000000

Only rejected communities release their name; a blocked community keeps it so
it cannot simply be created again.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8b5d3f0a7c2'
down_revision: Union[str, Sequence[str], None] = 'd7a4c2e9b6f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_index('uq_communities_name_active', table_name='communities', postgresql_where=sa.text("status NOT IN ('rejected', 'blocked')"))
    op.create_index('uq_communities_name_active', 'communities', [sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text("status <> 'rejected'"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_communities_name_active', table_name='communities', postgresql_where=sa.text("status <> 'rejected'"))
    op.create_index('uq_communities_name_active', 'communities', [sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text("status NOT IN ('rejected', 'blocked')"))
