"""add shipping address id to orders

Revision ID: e8b3d5f20a14
Revises: d6f1b3a95e20
Create Date: 2026-11-04 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e8b3d5f20a14'
down_revision: str | Sequence[str] | None = 'd6f1b3a95e20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('shipping_address_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_orders_shipping_address_id_user_addresses',
        'orders',
        'user_addresses',
        ['shipping_address_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_orders_shipping_address_id_user_addresses', 'orders', type_='foreignkey')
    op.drop_column('orders', 'shipping_address_id')
