"""add business verification

Revision ID: d3f5a7c9e1b2
Revises: bdfe0145c820
Create Date: 2026-10-28 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'd3f5a7c9e1b2'
down_revision: Union[str, Sequence[str], None] = 'bdfe0145c820'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

VERIFICATION_VALUES = ('pending', 'verified', 'rejected')


def upgrade() -> None:
    """Upgrade schema."""
    postgresql.ENUM(*VERIFICATION_VALUES, name='business_verification_status').create(op.get_bind())
    op.add_column(
        'businesses',
        sa.Column(
            'verification_status',
            postgresql.ENUM(*VERIFICATION_VALUES, name='business_verification_status', create_type=False),
            server_default='verified',
            nullable=False,
        ),
    )
    op.alter_column('businesses', 'verification_status', server_default=None)
    op.add_column('businesses', sa.Column('reviewed_by', sa.Uuid(), nullable=True))
    op.add_column('businesses', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('businesses', sa.Column('review_note', sa.Text(), nullable=True))
    op.add_column(
        'businesses',
        sa.Column('resubmission_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    )
    op.create_foreign_key(
        'businesses_reviewed_by_fkey',
        'businesses',
        'users',
        ['reviewed_by'],
        ['id'],
        ondelete='SET NULL',
    )
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'business_approved'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'business_rejected'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('businesses_reviewed_by_fkey', 'businesses', type_='foreignkey')
    op.drop_column('businesses', 'resubmission_count')
    op.drop_column('businesses', 'review_note')
    op.drop_column('businesses', 'reviewed_at')
    op.drop_column('businesses', 'reviewed_by')
    op.drop_column('businesses', 'verification_status')
    postgresql.ENUM(*VERIFICATION_VALUES, name='business_verification_status').drop(op.get_bind())
