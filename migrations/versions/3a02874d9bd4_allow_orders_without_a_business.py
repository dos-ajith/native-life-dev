"""allow orders without a business

Revision ID: 3a02874d9bd4
Revises: e4b8c27d91a6
Create Date: 2026-11-03 12:06:48.453069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a02874d9bd4'
down_revision: Union[str, Sequence[str], None] = 'e4b8c27d91a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('order_items', 'product_id', existing_type=sa.UUID(), nullable=True)
    op.alter_column('orders', 'business_id', existing_type=sa.UUID(), nullable=True)
    op.create_check_constraint(
        'ck_orders_business_required_unless_deal',
        'orders',
        "business_id IS NOT NULL OR order_type = 'deal'",
    )


def downgrade() -> None:
    op.drop_constraint('ck_orders_business_required_unless_deal', 'orders', type_='check')
    op.alter_column('orders', 'business_id', existing_type=sa.UUID(), nullable=False)
    op.alter_column('order_items', 'product_id', existing_type=sa.UUID(), nullable=False)
