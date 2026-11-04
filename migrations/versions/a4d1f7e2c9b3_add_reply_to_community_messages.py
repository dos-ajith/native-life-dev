"""add reply_to to community messages

Revision ID: a4d1f7e2c9b3
Revises: f2b8d5c3a7e1
Create Date: 2026-10-14 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a4d1f7e2c9b3'
down_revision: Union[str, Sequence[str], None] = 'f2b8d5c3a7e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('community_messages', sa.Column('reply_to_id', sa.Uuid(), nullable=True))
    op.create_index('ix_community_messages_reply_to_id', 'community_messages', ['reply_to_id'], unique=False)
    op.create_foreign_key('fk_community_messages_reply_to_id', 'community_messages', 'community_messages', ['reply_to_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_community_messages_reply_to_id', 'community_messages', type_='foreignkey')
    op.drop_index('ix_community_messages_reply_to_id', table_name='community_messages')
    op.drop_column('community_messages', 'reply_to_id')
