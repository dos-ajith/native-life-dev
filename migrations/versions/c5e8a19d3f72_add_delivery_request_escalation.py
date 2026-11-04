"""add delivery request escalation

Revision ID: c5e8a19d3f72
Revises: b7c3d91e5a24
Create Date: 2026-11-03 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5e8a19d3f72'
down_revision: Union[str, Sequence[str], None] = 'b7c3d91e5a24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('delivery_requests', sa.Column('escalated_at', sa.DateTime(), nullable=True))
    op.add_column('delivery_requests', sa.Column('passed_over_promoter_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'fk_delivery_requests_passed_over_promoter_id_users',
        'delivery_requests',
        'users',
        ['passed_over_promoter_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint(
        'fk_delivery_requests_passed_over_promoter_id_users', 'delivery_requests', type_='foreignkey'
    )
    op.drop_column('delivery_requests', 'passed_over_promoter_id')
    op.drop_column('delivery_requests', 'escalated_at')
