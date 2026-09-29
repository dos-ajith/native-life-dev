"""create emails table

Revision ID: 3c2ed1a58c49
Revises: a29aed2c9862
Create Date: 2026-09-29 10:59:47.622022

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '3c2ed1a58c49'
down_revision: Union[str, Sequence[str], None] = 'a29aed2c9862'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


email_type_enum = postgresql.ENUM(
    'email_verification', name='email_type', create_type=False
)
email_status_enum = postgresql.ENUM(
    'pending', 'sent', 'delivered', 'failed', 'bounced', 'rejected',
    name='email_status', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    email_type_enum.create(bind, checkfirst=True)
    email_status_enum.create(bind, checkfirst=True)

    op.create_table('emails',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('to_email', sa.String(length=255), nullable=False),
    sa.Column('from_email', sa.String(length=255), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('email_type', email_type_enum, nullable=False),
    sa.Column('provider', sa.String(length=50), nullable=False),
    sa.Column('provider_message_id', sa.String(length=255), nullable=True),
    sa.Column('status', email_status_enum, nullable=False),
    sa.Column('error_code', sa.String(length=100), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('sent_at', sa.DateTime(), nullable=True),
    sa.Column('delivered_at', sa.DateTime(), nullable=True),
    sa.Column('failed_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_emails_created_at', 'emails', ['created_at'], unique=False)
    op.create_index('ix_emails_email_type', 'emails', ['email_type'], unique=False)
    op.create_index('ix_emails_provider_message_id', 'emails', ['provider_message_id'], unique=True)
    op.create_index('ix_emails_status', 'emails', ['status'], unique=False)
    op.create_index(op.f('ix_emails_user_id'), 'emails', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_emails_user_id'), table_name='emails')
    op.drop_index('ix_emails_status', table_name='emails')
    op.drop_index('ix_emails_provider_message_id', table_name='emails')
    op.drop_index('ix_emails_email_type', table_name='emails')
    op.drop_index('ix_emails_created_at', table_name='emails')
    op.drop_table('emails')

    bind = op.get_bind()
    email_status_enum.drop(bind, checkfirst=True)
    email_type_enum.drop(bind, checkfirst=True)
