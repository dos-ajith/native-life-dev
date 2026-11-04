"""create native places tables

Revision ID: edc738870d55
Revises: 4dd605bf5e34
Create Date: 2026-10-13 12:24:57.021888

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'edc738870d55'
down_revision: Union[str, Sequence[str], None] = '4dd605bf5e34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('native_place_suggestions',
    sa.Column('name', sa.String(length=150), nullable=False),
    sa.Column('district_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='native_place_suggestion_status'), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['district_id'], ['gis_districts.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('user_native_places',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('taluk_id', sa.Uuid(), nullable=False),
    sa.Column('slot', sa.Enum('primary', 'secondary', name='native_place_slot'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['taluk_id'], ['gis_taluks.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'slot', name='uq_user_native_places_user_id_slot'),
    sa.UniqueConstraint('user_id', 'taluk_id', name='uq_user_native_places_user_id_taluk_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('user_native_places')
    op.drop_table('native_place_suggestions')
    sa.Enum(name='native_place_slot').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='native_place_suggestion_status').drop(op.get_bind(), checkfirst=True)
