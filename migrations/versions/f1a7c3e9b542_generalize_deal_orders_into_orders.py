"""generalize deal orders into orders

Revision ID: f1a7c3e9b542
Revises: e4b8d2f6a913
Create Date: 2026-10-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f1a7c3e9b542'
down_revision: Union[str, Sequence[str], None] = 'e4b8d2f6a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT_RENAMES = [
    ('deal_order_items', 'deal_order_items_pkey', 'order_items_pkey'),
    ('deal_order_items', 'deal_order_items_deal_item_id_fkey', 'order_items_deal_item_id_fkey'),
    ('deal_order_items', 'deal_order_items_order_id_fkey', 'order_items_order_id_fkey'),
    ('deal_orders', 'deal_orders_pkey', 'orders_pkey'),
    ('deal_orders', 'deal_orders_order_number_key', 'orders_order_number_key'),
    ('deal_orders', 'deal_orders_business_id_fkey', 'orders_business_id_fkey'),
    ('deal_orders', 'deal_orders_customer_id_fkey', 'orders_customer_id_fkey'),
    ('deal_orders', 'deal_orders_deal_id_fkey', 'orders_deal_id_fkey'),
]
INDEX_RENAMES = [
    ('ix_deal_order_items_deal_item_id', 'ix_order_items_deal_item_id'),
    ('ix_deal_orders_business_id', 'ix_orders_business_id'),
    ('ix_deal_orders_customer_id', 'ix_orders_customer_id'),
]


def upgrade() -> None:
    """Upgrade schema."""
    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {old} TO {new}')
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX {old} RENAME TO {new}')
    op.rename_table('deal_orders', 'orders')
    op.rename_table('deal_order_items', 'order_items')
    op.execute('ALTER TYPE deal_order_status RENAME TO order_status')
    order_type = postgresql.ENUM('deal', 'direct', name='order_type')
    order_type.create(op.get_bind())
    op.add_column(
        'orders',
        sa.Column(
            'order_type',
            postgresql.ENUM('deal', 'direct', name='order_type', create_type=False),
            server_default='deal',
            nullable=False,
        ),
    )
    op.alter_column('orders', 'order_type', server_default=None)
    op.alter_column('orders', 'deal_id', existing_type=sa.Uuid(), nullable=True)
    op.alter_column('order_items', 'deal_item_id', existing_type=sa.Uuid(), nullable=True)
    op.create_check_constraint(
        'ck_orders_deal_id_matches_type',
        'orders',
        "(order_type = 'deal') = (deal_id IS NOT NULL)",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_orders_deal_id_matches_type', 'orders', type_='check')
    op.alter_column('order_items', 'deal_item_id', existing_type=sa.Uuid(), nullable=False)
    op.alter_column('orders', 'deal_id', existing_type=sa.Uuid(), nullable=False)
    op.drop_column('orders', 'order_type')
    postgresql.ENUM(name='order_type').drop(op.get_bind(), checkfirst=False)
    op.execute('ALTER TYPE order_status RENAME TO deal_order_status')
    op.rename_table('order_items', 'deal_order_items')
    op.rename_table('orders', 'deal_orders')
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX {new} RENAME TO {old}')
    for table, old, new in CONSTRAINT_RENAMES:
        op.execute(f'ALTER TABLE {table} RENAME CONSTRAINT {new} TO {old}')
