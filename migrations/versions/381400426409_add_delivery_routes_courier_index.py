"""add delivery routes courier index

Revision ID: 381400426409
Revises: a7a438f1f6fd
Create Date: 2026-11-13 11:08:53.155252

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '381400426409'
down_revision: Union[str, Sequence[str], None] = 'a7a438f1f6fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None




def upgrade() -> None:
    """Upgrade schema."""
    op.create_index('ix_delivery_routes_courier_id', 'delivery_routes', ['courier_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_delivery_routes_courier_id', table_name='delivery_routes')
