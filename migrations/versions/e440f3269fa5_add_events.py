"""add events

Revision ID: e440f3269fa5
Revises: a1c7e5d9b3f2
Create Date: 2026-10-16 12:50:35.889190

"""
from typing import Sequence, Union

from alembic import op
from geoalchemy2 import Geometry
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e440f3269fa5'
down_revision: Union[str, Sequence[str], None] = 'a1c7e5d9b3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('events',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('organizer_name', sa.String(length=150), nullable=False),
    sa.Column('organizer_phone', sa.String(length=30), nullable=True),
    sa.Column('venue_name', sa.String(length=500), nullable=False),
    sa.Column('location', Geometry(geometry_type='POINT', srid=4326, spatial_index=False), nullable=False),
    sa.Column('starts_at', sa.DateTime(), nullable=False),
    sa.Column('ends_at', sa.DateTime(), nullable=False),
    sa.Column('status', sa.Enum('scheduled', 'cancelled', name='event_status'), nullable=False),
    sa.Column('is_featured', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_events_category_id', 'events', ['category_id'], unique=False)
    op.create_index('ix_events_starts_at', 'events', ['starts_at'], unique=False)
    op.create_index('ix_events_user_id', 'events', ['user_id'], unique=False)
    op.create_index(
        'ix_events_location_geography',
        'events',
        [sa.literal_column('(location::geography)')],
        unique=False,
        postgresql_using='gist',
    )
    op.create_table('event_images',
    sa.Column('event_id', sa.Uuid(), nullable=False),
    sa.Column('image_url', sa.String(length=2048), nullable=False),
    sa.Column('caption', sa.String(length=100), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_event_images_event_id', 'event_images', ['event_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_event_images_event_id', table_name='event_images')
    op.drop_table('event_images')
    op.drop_index('ix_events_location_geography', table_name='events', postgresql_using='gist')
    op.drop_index('ix_events_user_id', table_name='events')
    op.drop_index('ix_events_starts_at', table_name='events')
    op.drop_index('ix_events_category_id', table_name='events')
    op.drop_table('events')
    op.execute('DROP TYPE event_status')
