"""add delivery handover proof

Revision ID: 1a8f013b0500
Revises: 606575cadb5b
Create Date: 2026-11-13 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1a8f013b0500'
down_revision: Union[str, Sequence[str], None] = '606575cadb5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE delivery_request_status ADD VALUE IF NOT EXISTS 'delivered'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'delivery_started'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'delivery_delivered'")
    op.add_column('delivery_requests', sa.Column('started_at', sa.DateTime(), nullable=True))
    op.add_column('delivery_requests', sa.Column('delivered_at', sa.DateTime(), nullable=True))
    op.add_column(
        'delivery_requests',
        sa.Column('handover_otp_version', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    )
    op.add_column(
        'delivery_requests',
        sa.Column('handover_otp_attempts', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    )
    op.add_column('delivery_requests', sa.Column('proof_image_path', sa.String(length=512), nullable=True))
    op.add_column('delivery_requests', sa.Column('delivered_by_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('delivery_requests_delivered_by_id_fkey'),
        'delivery_requests',
        'users',
        ['delivered_by_id'],
        ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('delivery_requests_delivered_by_id_fkey'), 'delivery_requests', type_='foreignkey')
    op.drop_column('delivery_requests', 'delivered_by_id')
    op.drop_column('delivery_requests', 'proof_image_path')
    op.drop_column('delivery_requests', 'handover_otp_attempts')
    op.drop_column('delivery_requests', 'handover_otp_version')
    op.drop_column('delivery_requests', 'delivered_at')
    op.drop_column('delivery_requests', 'started_at')
