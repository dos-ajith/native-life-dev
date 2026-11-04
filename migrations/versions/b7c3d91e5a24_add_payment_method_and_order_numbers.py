"""add payment method, expected delivery and order number sequence

Revision ID: b7c3d91e5a24
Revises: 3a02874d9bd4
Create Date: 2026-11-03 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b7c3d91e5a24'
down_revision: Union[str, Sequence[str], None] = '3a02874d9bd4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

payment_method = postgresql.ENUM('cash_on_delivery', name='payment_method', create_type=False)


def upgrade() -> None:
    op.execute("CREATE SEQUENCE order_number_seq START 2001")
    postgresql.ENUM('cash_on_delivery', name='payment_method').create(op.get_bind(), checkfirst=True)
    op.add_column(
        'orders',
        sa.Column('payment_method', payment_method, server_default='cash_on_delivery', nullable=False),
    )
    op.add_column('orders', sa.Column('expected_delivery_date', sa.Date(), nullable=True))
    op.add_column('orders', sa.Column('expected_delivery_from', sa.Time(), nullable=True))
    op.add_column('orders', sa.Column('expected_delivery_to', sa.Time(), nullable=True))


def downgrade() -> None:
    op.drop_column('orders', 'expected_delivery_to')
    op.drop_column('orders', 'expected_delivery_from')
    op.drop_column('orders', 'expected_delivery_date')
    op.drop_column('orders', 'payment_method')
    postgresql.ENUM(name='payment_method').drop(op.get_bind(), checkfirst=True)
    op.execute("DROP SEQUENCE order_number_seq")
