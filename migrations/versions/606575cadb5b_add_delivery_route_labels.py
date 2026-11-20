"""add delivery route labels

Revision ID: 606575cadb5b
Revises: 381400426409
Create Date: 2026-11-13 12:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '606575cadb5b'
down_revision: Union[str, Sequence[str], None] = '381400426409'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('delivery_routes', sa.Column('start_label', sa.String(length=150), nullable=True))
    op.add_column('delivery_routes', sa.Column('end_label', sa.String(length=150), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('delivery_routes', 'end_label')
    op.drop_column('delivery_routes', 'start_label')
