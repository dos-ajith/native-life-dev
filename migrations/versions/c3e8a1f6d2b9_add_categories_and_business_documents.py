"""add categories and business documents

Revision ID: c3e8a1f6d2b9
Revises: b7c1d9e4a2f5
Create Date: 2026-10-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3e8a1f6d2b9'
down_revision: Union[str, Sequence[str], None] = 'b7c1d9e4a2f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


business_document_status_enum = postgresql.ENUM(
    'pending', 'under_review', 'verified', 'rejected',
    name='business_document_status', create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('categories',
    sa.Column('parent_id', sa.Uuid(), nullable=True),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    )
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

    op.add_column('businesses', sa.Column('category_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'businesses_category_id_fkey', 'businesses', 'categories', ['category_id'], ['id'],
        ondelete='RESTRICT',
    )
    op.create_index('ix_businesses_category_id', 'businesses', ['category_id'], unique=False)

    bind = op.get_bind()
    business_document_status_enum.create(bind, checkfirst=True)
    op.create_table('business_documents',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('document_type', sa.String(length=100), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('status', business_document_status_enum, nullable=False),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_business_documents_business_id', 'business_documents', ['business_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_business_documents_business_id', table_name='business_documents')
    op.drop_table('business_documents')
    business_document_status_enum.drop(op.get_bind(), checkfirst=True)

    op.drop_index('ix_businesses_category_id', table_name='businesses')
    op.drop_constraint('businesses_category_id_fkey', 'businesses', type_='foreignkey')
    op.drop_column('businesses', 'category_id')

    op.drop_index('uq_categories_root_name', table_name='categories')
    op.drop_index('uq_categories_parent_id_name', table_name='categories')
    op.drop_table('categories')
