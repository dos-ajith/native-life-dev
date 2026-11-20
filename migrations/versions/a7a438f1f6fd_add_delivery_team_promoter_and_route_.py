"""add delivery team promoter and route courier

Revision ID: a7a438f1f6fd
Revises: 7b1d4c9a2e60
Create Date: 2026-11-13 10:32:23.361721

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a7a438f1f6fd'
down_revision: Union[str, Sequence[str], None] = '7b1d4c9a2e60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('promoter_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('users_promoter_id_fkey'), 'users', 'users', ['promoter_id'], ['id'], ondelete='SET NULL'
    )
    op.add_column('delivery_routes', sa.Column('courier_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('delivery_routes_courier_id_fkey'),
        'delivery_routes',
        'users',
        ['courier_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('delivery_routes_courier_id_fkey'), 'delivery_routes', type_='foreignkey')
    op.drop_column('delivery_routes', 'courier_id')
    op.drop_constraint(op.f('users_promoter_id_fkey'), 'users', type_='foreignkey')
    op.drop_column('users', 'promoter_id')
