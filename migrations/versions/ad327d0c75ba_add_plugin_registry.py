"""add plugin registry

Revision ID: ad327d0c75ba
Revises: a9c4e2b7d815
Create Date: 2026-10-21 21:28:06.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'ad327d0c75ba'
down_revision: Union[str, Sequence[str], None] = 'a9c4e2b7d815'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('plugins',
    sa.Column('key', sa.String(length=30), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('business_type', sa.Enum('product', 'service', name='plugin_business_type'), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('status', sa.Enum('installed', 'enabled', 'disabled', name='plugin_status'), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('manifest', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('enabled_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    op.create_table('plugin_installations',
    sa.Column('plugin_key', sa.String(length=30), nullable=False),
    sa.Column('plugin_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.Enum('install', 'upgrade', 'reapply', 'downgrade', name='plugin_installation_action'), nullable=False),
    sa.Column('status', sa.Enum('succeeded', 'failed', name='plugin_installation_status'), nullable=False),
    sa.Column('from_version', sa.String(length=50), nullable=True),
    sa.Column('to_version', sa.String(length=50), nullable=False),
    sa.Column('content_sha256', sa.String(length=64), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['plugin_id'], ['plugins.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('plugin_installations')
    op.drop_table('plugins')
    op.execute('DROP TYPE plugin_installation_status')
    op.execute('DROP TYPE plugin_installation_action')
    op.execute('DROP TYPE plugin_status')
    op.execute('DROP TYPE plugin_business_type')
