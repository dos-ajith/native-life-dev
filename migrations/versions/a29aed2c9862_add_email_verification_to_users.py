"""add email verification to users

Revision ID: a29aed2c9862
Revises: f7e701eda49d
Create Date: 2026-09-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a29aed2c9862'
down_revision: Union[str, Sequence[str], None] = 'f7e701eda49d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(), nullable=True))
    op.create_table(
        'email_verification_otps',
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('otp_hash', sa.String(length=255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_email_verification_otps_user_id',
        'email_verification_otps',
        ['user_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_email_verification_otps_user_id', table_name='email_verification_otps')
    op.drop_table('email_verification_otps')
    op.drop_column('users', 'email_verified_at')
