"""create user addresses

Revision ID: bdfe0145c820
Revises: f1a7c3e9b542
Create Date: 2026-10-28 10:10:11.618685

"""
from typing import Sequence, Union

from alembic import op
import geoalchemy2
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'bdfe0145c820'
down_revision: Union[str, Sequence[str], None] = 'f1a7c3e9b542'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _point(name: str, nullable: bool) -> sa.Column:
    return sa.Column(
        name,
        geoalchemy2.Geometry(
            geometry_type='POINT',
            srid=4326,
            dimension=2,
            spatial_index=False,
            from_text='ST_GeomFromEWKT',
            name='geometry',
        ),
        nullable=nullable,
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_addresses',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('label', sa.String(length=50), nullable=False),
    sa.Column('full_name', sa.String(length=150), nullable=False),
    sa.Column('phone', sa.String(length=30), nullable=False),
    sa.Column('address_line', sa.String(length=255), nullable=False),
    sa.Column('landmark', sa.String(length=150), nullable=True),
    sa.Column('village_id', sa.Uuid(), nullable=False),
    _point('location', nullable=False),
    sa.Column('pincode', sa.String(length=6), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['village_id'], ['gis_villages.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_user_addresses_user_id', 'user_addresses', ['user_id'], unique=False)
    op.add_column('orders', _point('shipping_location', nullable=True))
    op.add_column('orders', sa.Column('shipping_village_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'orders_shipping_village_id_fkey',
        'orders',
        'gis_villages',
        ['shipping_village_id'],
        ['id'],
        ondelete='RESTRICT',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('orders_shipping_village_id_fkey', 'orders', type_='foreignkey')
    op.drop_column('orders', 'shipping_village_id')
    op.drop_column('orders', 'shipping_location')
    op.drop_index('ix_user_addresses_user_id', table_name='user_addresses')
    op.drop_table('user_addresses')
