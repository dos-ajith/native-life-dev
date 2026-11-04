"""create businesses table

Revision ID: b7c1d9e4a2f5
Revises: 410345c8d288
Create Date: 2026-10-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7c1d9e4a2f5'
down_revision: Union[str, Sequence[str], None] = '410345c8d288'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


business_status_enum = postgresql.ENUM(
    'active', 'inactive', name='business_status', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    business_status_enum.create(bind, checkfirst=True)

    op.create_table('businesses',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', business_status_enum, nullable=False),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_businesses_owner_id', 'businesses', ['owner_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_businesses_owner_id', table_name='businesses')
    op.drop_table('businesses')
    business_status_enum.drop(op.get_bind(), checkfirst=True)
