"""add business escalation

Revision ID: b4e81f20c6a3
Revises: a7c3d91e5b20
Create Date: 2026-10-30 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4e81f20c6a3'
down_revision: Union[str, Sequence[str], None] = 'a7c3d91e5b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('businesses', sa.Column('escalated_at', sa.DateTime(), nullable=True))
    op.add_column('businesses', sa.Column('escalated_by', sa.UUID(), nullable=True))
    op.add_column('businesses', sa.Column('escalation_note', sa.Text(), nullable=True))
    op.create_foreign_key(
        'businesses_escalated_by_fkey',
        'businesses',
        'users',
        ['escalated_by'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('businesses_escalated_by_fkey', 'businesses', type_='foreignkey')
    op.drop_column('businesses', 'escalation_note')
    op.drop_column('businesses', 'escalated_by')
    op.drop_column('businesses', 'escalated_at')
