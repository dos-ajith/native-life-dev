"""add order tax amounts

Revision ID: 7b1d4c9a2e60
Revises: 4550a302ceb9
Create Date: 2026-11-12 11:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7b1d4c9a2e60'
down_revision: Union[str, Sequence[str], None] = '4550a302ceb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('orders', sa.Column('tax_amount', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False))
    op.add_column('order_items', sa.Column('tax_percent', sa.Numeric(precision=5, scale=2), server_default=sa.text('0'), nullable=False))
    op.add_column('order_items', sa.Column('tax_amount', sa.Numeric(precision=14, scale=2), server_default=sa.text('0'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('order_items', 'tax_amount')
    op.drop_column('order_items', 'tax_percent')
    op.drop_column('orders', 'tax_amount')
