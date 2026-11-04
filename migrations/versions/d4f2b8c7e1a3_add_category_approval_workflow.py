"""add category approval workflow

Revision ID: d4f2b8c7e1a3
Revises: c3e8a1f6d2b9
Create Date: 2026-10-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd4f2b8c7e1a3'
down_revision: Union[str, Sequence[str], None] = 'c3e8a1f6d2b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


category_status_enum = postgresql.ENUM(
    'pending', 'published', 'rejected', name='category_status', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    category_status_enum.create(bind, checkfirst=True)

    op.add_column(
        'categories',
        sa.Column('status', category_status_enum, server_default='published', nullable=False),
    )
    op.alter_column('categories', 'status', server_default=None)

    op.add_column('categories', sa.Column('created_by', sa.Uuid(), nullable=True))
    op.add_column('categories', sa.Column('reviewed_by', sa.Uuid(), nullable=True))
    op.add_column('categories', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('categories', sa.Column('review_note', sa.Text(), nullable=True))
    op.create_foreign_key(
        'categories_created_by_fkey', 'categories', 'users', ['created_by'], ['id'],
        ondelete='SET NULL',
    )
    op.create_foreign_key(
        'categories_reviewed_by_fkey', 'categories', 'users', ['reviewed_by'], ['id'],
        ondelete='SET NULL',
    )

    op.drop_index('uq_categories_root_name', table_name='categories')
    op.drop_index('uq_categories_parent_id_name', table_name='categories')
    op.create_index(
        'uq_categories_parent_id_name',
        'categories',
        ['parent_id', sa.text('lower(name)')],
        unique=True,
        postgresql_where=sa.text("parent_id IS NOT NULL AND status <> 'rejected'"),
    )
    op.create_index(
        'uq_categories_root_name',
        'categories',
        [sa.text('lower(name)')],
        unique=True,
        postgresql_where=sa.text("parent_id IS NULL AND status <> 'rejected'"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DELETE FROM categories WHERE status <> 'published'")
    op.drop_index('uq_categories_root_name', table_name='categories')
    op.drop_index('uq_categories_parent_id_name', table_name='categories')
    op.create_index(
        'uq_categories_parent_id_name',
        'categories',
        ['parent_id', sa.text('lower(name)')],
        unique=True,
        postgresql_where=sa.text('parent_id IS NOT NULL'),
    )
    op.create_index(
        'uq_categories_root_name',
        'categories',
        [sa.text('lower(name)')],
        unique=True,
        postgresql_where=sa.text('parent_id IS NULL'),
    )

    op.drop_constraint('categories_reviewed_by_fkey', 'categories', type_='foreignkey')
    op.drop_constraint('categories_created_by_fkey', 'categories', type_='foreignkey')
    op.drop_column('categories', 'review_note')
    op.drop_column('categories', 'reviewed_at')
    op.drop_column('categories', 'reviewed_by')
    op.drop_column('categories', 'created_by')
    op.drop_column('categories', 'status')
    category_status_enum.drop(op.get_bind(), checkfirst=True)
