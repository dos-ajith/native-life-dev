"""add direct chat and user blocks

Revision ID: 9c69c70403ba
Revises: f2a6c8d41b37
Create Date: 2026-11-04 13:59:52.409701

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9c69c70403ba'
down_revision: Union[str, Sequence[str], None] = 'f2a6c8d41b37'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MESSAGE_PERMISSION_VALUES = ('everyone', 'connections')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('chat_conversations',
    sa.Column('lower_user_id', sa.Uuid(), nullable=False),
    sa.Column('higher_user_id', sa.Uuid(), nullable=False),
    sa.Column('last_message_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('lower_user_id < higher_user_id', name='ck_chat_conversations_ordered'),
    sa.ForeignKeyConstraint(['higher_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['lower_user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lower_user_id', 'higher_user_id', name='uq_chat_conversations_lower_user_id_higher')
    )
    op.create_index('ix_chat_conversations_higher_user_id', 'chat_conversations', ['higher_user_id'], unique=False)
    op.create_table('user_blocks',
    sa.Column('blocker_id', sa.Uuid(), nullable=False),
    sa.Column('blocked_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('blocker_id <> blocked_id', name='ck_user_blocks_not_self'),
    sa.ForeignKeyConstraint(['blocked_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['blocker_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_user_blocks_blocker_id_blocked_id')
    )
    op.create_table('direct_messages',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('sender_id', sa.Uuid(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['chat_conversations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_direct_messages_conversation_id_created_at', 'direct_messages', ['conversation_id', 'created_at'], unique=False)
    postgresql.ENUM(*MESSAGE_PERMISSION_VALUES, name='message_permission').create(op.get_bind())
    op.add_column(
        'user_privacy_settings',
        sa.Column(
            'who_can_message',
            postgresql.ENUM(*MESSAGE_PERMISSION_VALUES, name='message_permission', create_type=False),
            server_default='everyone',
            nullable=False,
        ),
    )
    op.alter_column('user_privacy_settings', 'who_can_message', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_privacy_settings', 'who_can_message')
    postgresql.ENUM(*MESSAGE_PERMISSION_VALUES, name='message_permission').drop(op.get_bind())
    op.drop_index('ix_direct_messages_conversation_id_created_at', table_name='direct_messages')
    op.drop_table('direct_messages')
    op.drop_table('user_blocks')
    op.drop_index('ix_chat_conversations_higher_user_id', table_name='chat_conversations')
    op.drop_table('chat_conversations')
