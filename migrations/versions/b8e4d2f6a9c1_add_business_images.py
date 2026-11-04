"""add business images

Revision ID: b8e4d2f6a9c1
Revises: a7d3c9e5b1f4
Create Date: 2026-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b8e4d2f6a9c1'
down_revision: Union[str, Sequence[str], None] = 'a7d3c9e5b1f4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('business_images',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('image_url', sa.String(length=2048), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_business_images_business_id', 'business_images', ['business_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_business_images_business_id', table_name='business_images')
    op.drop_table('business_images')
