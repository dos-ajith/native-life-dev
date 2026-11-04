"""add delivery settings and order delivery

Revision ID: 60a55a713bf5
Revises: 59c1bd8e28d6
Create Date: 2026-10-28 15:32:14.552905

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '60a55a713bf5'
down_revision: Union[str, Sequence[str], None] = '59c1bd8e28d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

delivery_option = postgresql.ENUM('instant', 'route', 'self_pickup', name='delivery_option', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('delivery_settings',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('working_days', postgresql.ARRAY(sa.SmallInteger()), nullable=False),
    sa.Column('route_start_time', sa.Time(), nullable=False),
    sa.Column('route_end_time', sa.Time(), nullable=False),
    sa.Column('instant_fee', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('route_fee', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_delivery_settings_user_id')
    )
    delivery_option.create(op.get_bind(), checkfirst=True)
    op.add_column('orders', sa.Column('promoter_id', sa.Uuid(), nullable=True))
    op.add_column('orders', sa.Column('delivery_option', delivery_option, nullable=True))
    op.add_column('orders', sa.Column('delivery_fee', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False))
    op.create_foreign_key('orders_promoter_id_fkey', 'orders', 'users', ['promoter_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('orders_promoter_id_fkey', 'orders', type_='foreignkey')
    op.drop_column('orders', 'delivery_fee')
    op.drop_column('orders', 'delivery_option')
    op.drop_column('orders', 'promoter_id')
    delivery_option.drop(op.get_bind(), checkfirst=True)
    op.drop_table('delivery_settings')
