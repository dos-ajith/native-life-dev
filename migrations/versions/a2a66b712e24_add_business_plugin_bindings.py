"""add business plugin bindings

Revision ID: a2a66b712e24
Revises: ad327d0c75ba
Create Date: 2026-10-22 09:30:03.863824

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2a66b712e24'
down_revision: Union[str, Sequence[str], None] = 'ad327d0c75ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('categories', sa.Column('sort_order', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.create_table('plugin_category_bindings',
    sa.Column('plugin_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('ownership', sa.Enum('created', 'adopted', name='plugin_category_ownership'), nullable=False),
    sa.Column('applies_to_businesses', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('include_descendants', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('removed_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('plugin_id', 'category_id', name='uq_plugin_category_bindings_plugin_id_category_id')
    )
    op.create_index('ix_plugin_category_bindings_category_id', 'plugin_category_bindings', ['category_id'], unique=False)
    op.create_table('business_plugins',
    sa.Column('business_id', sa.Uuid(), nullable=False),
    sa.Column('plugin_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('active', 'disabled', name='business_plugin_status'), nullable=False),
    sa.Column('enabled_by', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['enabled_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('business_id', 'plugin_id', name='uq_business_plugins_business_id_plugin_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('business_plugins')
    op.drop_index('ix_plugin_category_bindings_category_id', table_name='plugin_category_bindings')
    op.drop_table('plugin_category_bindings')
    op.drop_column('categories', 'sort_order')
    op.execute('DROP TYPE business_plugin_status')
    op.execute('DROP TYPE plugin_category_ownership')
