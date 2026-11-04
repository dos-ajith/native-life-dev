"""add deal item product id

Revision ID: c7e3a91d5b24
Revises: a2a66b712e24
Create Date: 2026-10-27 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e3a91d5b24'
down_revision: Union[str, Sequence[str], None] = 'a2a66b712e24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('deal_items', sa.Column('product_id', sa.Uuid(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('deal_items', 'product_id')
