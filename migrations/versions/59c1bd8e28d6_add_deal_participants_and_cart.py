"""add deal participants and cart

Revision ID: 59c1bd8e28d6
Revises: d3f5a7c9e1b2
Create Date: 2026-10-28 14:43:39.453914

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '59c1bd8e28d6'
down_revision: Union[str, Sequence[str], None] = 'd3f5a7c9e1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('deals', sa.Column('joined_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.create_table('deal_participants',
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('deal_id', 'user_id', name='uq_deal_participants_deal_id_user_id')
    )
    op.create_index('ix_deal_participants_user_id', 'deal_participants', ['user_id'], unique=False)
    op.create_table('cart_items',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('deal_item_id', sa.Uuid(), nullable=False),
    sa.Column('quantity', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity > 0', name='ck_cart_items_quantity_positive'),
    sa.ForeignKeyConstraint(['deal_item_id'], ['deal_items.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'deal_item_id', name='uq_cart_items_user_id_deal_item_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('cart_items')
    op.drop_index('ix_deal_participants_user_id', table_name='deal_participants')
    op.drop_table('deal_participants')
    op.drop_column('deals', 'joined_count')
