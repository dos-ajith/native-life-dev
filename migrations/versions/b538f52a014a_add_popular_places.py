"""add popular places

Revision ID: b538f52a014a
Revises: e440f3269fa5
Create Date: 2026-10-19 10:15:49.473245

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b538f52a014a'
down_revision: Union[str, Sequence[str], None] = 'e440f3269fa5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('popular_places',
    sa.Column('village_id', sa.Uuid(), nullable=False),
    sa.Column('image_url', sa.String(length=2048), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['village_id'], ['gis_villages.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('village_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('popular_places')
