"""move polls into their own tables

Revision ID: b5e2a8d4f1c7
Revises: a4d1f7e2c9b3
Create Date: 2026-10-14 16:00:00.000000

Polls stop being a post type. Existing poll posts are copied into the new
community_polls tables with the same ids (so poll ids and option ids stay
valid), then the poll posts, the old poll tables and posts.post_type are removed.
The downgrade restores the old structure only; poll data is not copied back.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5e2a8d4f1c7'
down_revision: Union[str, Sequence[str], None] = 'a4d1f7e2c9b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('community_polls',
    sa.Column('community_id', sa.Uuid(), nullable=False),
    sa.Column('author_id', sa.Uuid(), nullable=False),
    sa.Column('question', sa.String(length=500), nullable=False),
    sa.Column('allows_multiple', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('show_results_before_vote', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_community_polls_community_id_created_at', 'community_polls', ['community_id', 'created_at'], unique=False)
    op.create_table('community_poll_options',
    sa.Column('poll_id', sa.Uuid(), nullable=False),
    sa.Column('text', sa.String(length=200), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('votes_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['poll_id'], ['community_polls.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_community_poll_options_poll_id', 'community_poll_options', ['poll_id'], unique=False)
    op.create_table('community_poll_votes',
    sa.Column('poll_id', sa.Uuid(), nullable=False),
    sa.Column('option_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['option_id'], ['community_poll_options.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['poll_id'], ['community_polls.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('option_id', 'user_id', name='uq_community_poll_votes_option_id_user_id')
    )
    op.create_index('ix_community_poll_votes_poll_id_user_id', 'community_poll_votes', ['poll_id', 'user_id'], unique=False)

    op.execute("""
        INSERT INTO community_polls
            (id, community_id, author_id, question, allows_multiple,
             show_results_before_vote, ends_at, created_at, updated_at)
        SELECT p.id, p.community_id, p.user_id, LEFT(COALESCE(p.content, ''), 500),
               pp.allows_multiple, pp.show_results_before_vote, pp.ends_at,
               COALESCE(p.published_at, p.created_at), p.updated_at
        FROM post_polls pp
        JOIN posts p ON p.id = pp.post_id
        WHERE p.community_id IS NOT NULL AND p.deleted_at IS NULL
    """)
    op.execute("""
        INSERT INTO community_poll_options (id, poll_id, text, position, votes_count)
        SELECT o.id, pp.post_id, o.text, o.position, o.votes_count
        FROM post_poll_options o
        JOIN post_polls pp ON pp.id = o.poll_id
        JOIN community_polls cp ON cp.id = pp.post_id
    """)
    op.execute("""
        INSERT INTO community_poll_votes (id, poll_id, option_id, user_id, created_at)
        SELECT v.id, pp.post_id, v.option_id, v.user_id, v.created_at
        FROM post_poll_votes v
        JOIN post_polls pp ON pp.id = v.poll_id
        JOIN community_polls cp ON cp.id = pp.post_id
    """)

    op.execute("DELETE FROM posts WHERE post_type = 'poll'")
    op.drop_table('post_poll_votes')
    op.drop_table('post_poll_options')
    op.drop_table('post_polls')
    op.drop_column('posts', 'post_type')
    op.execute("DROP TYPE post_type")


def downgrade() -> None:
    """Downgrade schema (structure only, poll data is not copied back)."""
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

    op.drop_index('ix_community_poll_votes_poll_id_user_id', table_name='community_poll_votes')
    op.drop_table('community_poll_votes')
    op.drop_index('ix_community_poll_options_poll_id', table_name='community_poll_options')
    op.drop_table('community_poll_options')
    op.drop_index('ix_community_polls_community_id_created_at', table_name='community_polls')
    op.drop_table('community_polls')
