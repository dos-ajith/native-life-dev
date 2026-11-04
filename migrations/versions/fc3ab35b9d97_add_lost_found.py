"""add lost found

Revision ID: fc3ab35b9d97
Revises: 7804541f5d7a
Create Date: 2026-10-16 10:28:37.271120

"""
from typing import Sequence, Union

from alembic import op
from geoalchemy2 import Geometry
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc3ab35b9d97'
down_revision: Union[str, Sequence[str], None] = '7804541f5d7a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('lost_found_items',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.Enum('lost', 'found', name='lost_found_kind'), nullable=False),
    sa.Column('status', sa.Enum('open', 'resolved', name='lost_found_status'), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('location_name', sa.String(length=500), nullable=False),
    sa.Column('location', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
    sa.Column('occurred_on', sa.Date(), nullable=False),
    sa.Column('contact_info', sa.String(length=150), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lost_found_items_category_id', 'lost_found_items', ['category_id'], unique=False)
    op.create_index('ix_lost_found_items_user_id', 'lost_found_items', ['user_id'], unique=False)
    op.create_index(
        'ix_lost_found_items_location_geography',
        'lost_found_items',
        [sa.literal_column('(location::geography)')],
        unique=False,
        postgresql_using='gist',
    )
    op.create_table('lost_found_images',
    sa.Column('item_id', sa.Uuid(), nullable=False),
    sa.Column('image_url', sa.String(length=2048), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['lost_found_items.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_lost_found_images_item_id', 'lost_found_images', ['item_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_lost_found_images_item_id', table_name='lost_found_images')
    op.drop_table('lost_found_images')
    op.drop_index('ix_lost_found_items_location_geography', table_name='lost_found_items', postgresql_using='gist')
    op.drop_index('ix_lost_found_items_user_id', table_name='lost_found_items')
    op.drop_index('ix_lost_found_items_category_id', table_name='lost_found_items')
    op.drop_table('lost_found_items')
    op.execute('DROP TYPE lost_found_status')
    op.execute('DROP TYPE lost_found_kind')
