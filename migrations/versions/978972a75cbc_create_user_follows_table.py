"""create user_follows table

Revision ID: 978972a75cbc
Revises: 7fb1ec477a03
Create Date: 2026-09-23 12:09:01.778876

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '978972a75cbc'
down_revision: Union[str, Sequence[str], None] = '7fb1ec477a03'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_follows',
    sa.Column('follower_id', sa.Uuid(), nullable=False),
    sa.Column('following_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('follower_id <> following_id', name='ck_user_follows_not_self'),
    sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['following_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('follower_id', 'following_id', name='uq_user_follows_follower_id_following_id')
    )
    op.create_index('ix_user_follows_following_id', 'user_follows', ['following_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_follows_following_id', table_name='user_follows')
    op.drop_table('user_follows')
