"""create notifications table

Revision ID: 692c0a5cdad6
Revises: 978972a75cbc
Create Date: 2026-09-24 09:59:36.590919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '692c0a5cdad6'
down_revision: Union[str, Sequence[str], None] = '978972a75cbc'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


notification_type_enum = postgresql.ENUM(
    'user_followed', 'post_liked', 'post_commented', name='notification_type', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    notification_type_enum.create(bind, checkfirst=True)

    op.create_table('notifications',
    sa.Column('recipient_id', sa.Uuid(), nullable=False),
    sa.Column('actor_id', sa.Uuid(), nullable=True),
    sa.Column('type', notification_type_enum, nullable=False),
    sa.Column('entity_type', sa.String(length=100), nullable=True),
    sa.Column('entity_id', sa.Uuid(), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('is_read', sa.Boolean(), nullable=False),
    sa.Column('read_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_created_at', 'notifications', ['created_at'], unique=False)
    op.create_index('ix_notifications_recipient_id', 'notifications', ['recipient_id'], unique=False)
    op.create_index(
        'ix_notifications_recipient_id_unread',
        'notifications',
        ['recipient_id'],
        unique=False,
        postgresql_where=sa.text('is_read IS FALSE'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_notifications_recipient_id_unread',
        table_name='notifications',
        postgresql_where=sa.text('is_read IS FALSE'),
    )
    op.drop_index('ix_notifications_recipient_id', table_name='notifications')
    op.drop_index('ix_notifications_created_at', table_name='notifications')
    op.drop_table('notifications')

    bind = op.get_bind()
    notification_type_enum.drop(bind, checkfirst=True)
