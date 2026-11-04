"""create community polls

Revision ID: d8b4f2a6c1e5
Revises: c3e8a1f5d7b9
Create Date: 2026-10-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8b4f2a6c1e5'
down_revision: Union[str, Sequence[str], None] = 'c3e8a1f5d7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    post_type = sa.Enum('standard', 'poll', name='post_type')
    post_type.create(op.get_bind(), checkfirst=True)
    op.add_column('posts', sa.Column('post_type', sa.Enum('standard', 'poll', name='post_type', create_type=False), server_default='standard', nullable=False))
    op.create_table('post_polls',
    sa.Column('post_id', sa.Uuid(), nullable=False),
    sa.Column('allows_multiple', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('show_results_before_vote', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('post_id')
    )
    op.create_table('post_poll_options',
    sa.Column('poll_id', sa.Uuid(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('votes_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['poll_id'], ['post_polls.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_post_poll_options_poll_id', 'post_poll_options', ['poll_id'], unique=False)
    op.create_table('post_poll_votes',
    sa.Column('poll_id', sa.Uuid(), nullable=False),
    sa.Column('option_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['post_poll_options.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['poll_id'], ['post_polls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('option_id', 'user_id', name='uq_post_poll_votes_option_id_user_id')
    )
    op.create_index('ix_post_poll_votes_poll_id_user_id', 'post_poll_votes', ['poll_id', 'user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_post_poll_votes_poll_id_user_id', table_name='post_poll_votes')
    op.drop_table('post_poll_votes')
    op.drop_index('ix_post_poll_options_poll_id', table_name='post_poll_options')
    op.drop_table('post_poll_options')
    op.drop_table('post_polls')
    op.drop_column('posts', 'post_type')
    op.execute("DROP TYPE post_type")
