"""create communities and community members

Revision ID: 9325539c08a3
Revises: b7d2e4f19a35
Create Date: 2026-10-14 10:28:54.087731

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9325539c08a3'
down_revision: Union[str, Sequence[str], None] = 'b7d2e4f19a35'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COMMUNITY_NOTIFICATION_TYPES = (
    'community_submitted',
    'community_approved',
    'community_rejected',
    'community_join_requested',
    'community_join_approved',
    'community_join_rejected',
    'community_post_removed',
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('communities',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('auto_approve_members', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('max_members', sa.Integer(), nullable=True),
    sa.Column('members_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
    sa.Column('status', sa.Enum('pending', 'published', 'rejected', name='community_status'), nullable=False),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_communities_owner_id', 'communities', ['owner_id'], unique=False)
    op.create_index('ix_communities_status', 'communities', ['status'], unique=False)
    op.create_index('uq_communities_name_active', 'communities', [sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text("status <> 'rejected'"))
    op.create_table('community_members',
    sa.Column('community_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'active', 'blocked', name='community_member_status'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['community_id'], ['communities.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('community_id', 'user_id', name='uq_community_members_community_user')
    )
    op.create_index('ix_community_members_user_id', 'community_members', ['user_id'], unique=False)
    op.add_column('posts', sa.Column('community_id', sa.Uuid(), nullable=True))
    op.add_column('posts', sa.Column('removed_by', sa.Uuid(), nullable=True))
    op.add_column('posts', sa.Column('removal_reason', sa.Text(), nullable=True))
    op.create_index('ix_posts_community_id_created_at', 'posts', ['community_id', 'created_at'], unique=False)
    op.create_foreign_key('fk_posts_community_id_communities', 'posts', 'communities', ['community_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_posts_removed_by_users', 'posts', 'users', ['removed_by'], ['id'], ondelete='SET NULL')
    for value in COMMUNITY_NOTIFICATION_TYPES:
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_posts_removed_by_users', 'posts', type_='foreignkey')
    op.drop_constraint('fk_posts_community_id_communities', 'posts', type_='foreignkey')
    op.drop_index('ix_posts_community_id_created_at', table_name='posts')
    op.drop_column('posts', 'removal_reason')
    op.drop_column('posts', 'removed_by')
    op.drop_column('posts', 'community_id')
    op.drop_index('ix_community_members_user_id', table_name='community_members')
    op.drop_table('community_members')
    op.drop_index('uq_communities_name_active', table_name='communities', postgresql_where=sa.text("status <> 'rejected'"))
    op.drop_index('ix_communities_status', table_name='communities')
    op.drop_index('ix_communities_owner_id', table_name='communities')
    op.drop_table('communities')
    op.execute("DROP TYPE community_member_status")
    op.execute("DROP TYPE community_status")
