"""add village to communities

Revision ID: c6f3b9a1d5e8
Revises: b5e2a8d4f1c7
Create Date: 2026-10-14 17:00:00.000000

Existing communities are linked to their owner's primary native place; any
owner without one leaves village_id empty (such communities are not recommended).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c6f3b9a1d5e8'
down_revision: Union[str, Sequence[str], None] = 'b5e2a8d4f1c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('communities', sa.Column('village_id', sa.Uuid(), nullable=True))
    op.create_index('ix_communities_village_id', 'communities', ['village_id'], unique=False)
    op.create_foreign_key('fk_communities_village_id_gis_villages', 'communities', 'gis_villages', ['village_id'], ['id'], ondelete='RESTRICT')
    op.execute("""
        UPDATE communities
        SET village_id = user_native_places.village_id
        FROM user_native_places
        WHERE user_native_places.user_id = communities.owner_id
          AND user_native_places.slot = 'primary'
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_communities_village_id_gis_villages', 'communities', type_='foreignkey')
    op.drop_index('ix_communities_village_id', table_name='communities')
    op.drop_column('communities', 'village_id')
