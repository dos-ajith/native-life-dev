"""add device tokens

Revision ID: c8d2f4a61b93
Revises: e4c0a2b8d6f3
Create Date: 2026-11-02 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c8d2f4a61b93'
down_revision: str | Sequence[str] | None = 'e4c0a2b8d6f3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('device_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token', sa.String(length=1024), nullable=False),
    sa.Column('platform', sa.Enum('android', 'ios', 'web', name='device_platform'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token')
    )
    op.create_index('ix_device_tokens_user_id', 'device_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_device_tokens_user_id', table_name='device_tokens')
    op.drop_table('device_tokens')
    sa.Enum(name='device_platform').drop(op.get_bind(), checkfirst=False)
