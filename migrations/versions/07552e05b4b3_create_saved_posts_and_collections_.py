"""create saved posts and collections tables

Revision ID: 07552e05b4b3
Revises: 6293c503ded0
Create Date: 2026-09-25 13:48:48.910611

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '07552e05b4b3'
down_revision: Union[str, Sequence[str], None] = '6293c503ded0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('collections',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_collections_user_id', 'collections', ['user_id'], unique=False)

    op.create_table('saved_posts',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('post_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'post_id', name='uq_saved_posts_user_id_post_id')
    )
    op.create_index('ix_saved_posts_post_id', 'saved_posts', ['post_id'], unique=False)
    op.create_index('ix_saved_posts_user_id', 'saved_posts', ['user_id'], unique=False)

    op.create_table('collection_posts',
    sa.Column('collection_id', sa.Uuid(), nullable=False),
    sa.Column('saved_post_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['collection_id'], ['collections.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['saved_post_id'], ['saved_posts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('collection_id', 'saved_post_id', name='uq_collection_posts_collection_id_saved_post_id')
    )
    op.create_index('ix_collection_posts_collection_id', 'collection_posts', ['collection_id'], unique=False)
    op.create_index('ix_collection_posts_saved_post_id', 'collection_posts', ['saved_post_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_collection_posts_saved_post_id', table_name='collection_posts')
    op.drop_index('ix_collection_posts_collection_id', table_name='collection_posts')
    op.drop_table('collection_posts')

    op.drop_index('ix_saved_posts_user_id', table_name='saved_posts')
    op.drop_index('ix_saved_posts_post_id', table_name='saved_posts')
    op.drop_table('saved_posts')

    op.drop_index('ix_collections_user_id', table_name='collections')
    op.drop_table('collections')
