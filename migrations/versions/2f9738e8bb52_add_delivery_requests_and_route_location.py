"""add delivery requests and route location

Revision ID: 2f9738e8bb52
Revises: 567687282bf2
Create Date: 2026-10-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2f9738e8bb52'
down_revision: Union[str, Sequence[str], None] = '567687282bf2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

delivery_option = postgresql.ENUM('instant', 'route', 'self_pickup', name='delivery_option', create_type=False)
delivery_request_status = postgresql.ENUM('requested', 'accepted', 'rejected', 'expired', 'cancelled', name='delivery_request_status', create_type=False)

NOTIFICATION_VALUES = ('delivery_requested', 'delivery_accepted', 'delivery_rejected', 'delivery_expired')


def upgrade() -> None:
    """Upgrade schema."""
    for value in NOTIFICATION_VALUES:
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column('delivery_routes', sa.Column('current_location', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, spatial_index=False, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True))
    op.add_column('delivery_routes', sa.Column('location_updated_at', sa.DateTime(), nullable=True))
    delivery_request_status.create(op.get_bind(), checkfirst=True)
    op.create_table('delivery_requests',
    sa.Column('order_id', sa.Uuid(), nullable=False),
    sa.Column('option', delivery_option, nullable=False),
    sa.Column('delivery_date', sa.Date(), nullable=False),
    sa.Column('route_id', sa.Uuid(), nullable=True),
    sa.Column('promoter_id', sa.Uuid(), nullable=True),
    sa.Column('status', delivery_request_status, nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['promoter_id'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['route_id'], ['delivery_routes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_delivery_requests_one_active_per_order', 'delivery_requests', ['order_id'], unique=True, postgresql_where=sa.text("status IN ('requested', 'accepted')"))
    op.create_index('ix_delivery_requests_promoter_id_status', 'delivery_requests', ['promoter_id', 'status'], unique=False)
    op.create_index('ix_delivery_requests_route_id_delivery_date', 'delivery_requests', ['route_id', 'delivery_date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_delivery_requests_route_id_delivery_date', table_name='delivery_requests')
    op.drop_index('ix_delivery_requests_promoter_id_status', table_name='delivery_requests')
    op.drop_index('uq_delivery_requests_one_active_per_order', table_name='delivery_requests', postgresql_where=sa.text("status IN ('requested', 'accepted')"))
    op.drop_table('delivery_requests')
    delivery_request_status.drop(op.get_bind(), checkfirst=True)
    op.drop_column('delivery_routes', 'location_updated_at')
    op.drop_column('delivery_routes', 'current_location')
