"""add deal form fields

Revision ID: a9c4e2b7d815
Revises: cc467734a535
Create Date: 2026-10-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a9c4e2b7d815'
down_revision: Union[str, Sequence[str], None] = 'cc467734a535'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('deals', sa.Column('min_joiners', sa.Integer(), nullable=True))
    op.add_column('deals', sa.Column('pickup_location', sa.String(length=500), nullable=True))
    op.add_column('deals', sa.Column('delivery_details', sa.Text(), nullable=True))
    op.add_column('deals', sa.Column('starts_at', sa.DateTime(), nullable=True))
    op.add_column('deal_items', sa.Column('unit', sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column('deal_items', 'unit')
    op.drop_column('deals', 'starts_at')
    op.drop_column('deals', 'delivery_details')
    op.drop_column('deals', 'pickup_location')
    op.drop_column('deals', 'min_joiners')
