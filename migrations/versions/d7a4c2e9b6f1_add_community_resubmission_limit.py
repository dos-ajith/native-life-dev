"""add community resubmission limit

Revision ID: d7a4c2e9b6f1
Revises: c6f3b9a1d5e8
Create Date: 2026-10-15 12:00:00.000000

A rejected community may be resubmitted a limited number of times; the
rejection after the last allowed resubmission sets it to blocked, which
(like rejected) releases its name.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a4c2e9b6f1'
down_revision: Union[str, Sequence[str], None] = 'c6f3b9a1d5e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE community_status ADD VALUE IF NOT EXISTS 'blocked'")
    op.add_column('communities', sa.Column('resubmission_count', sa.Integer(), server_default=sa.text('0'), nullable=False))
    op.drop_index('uq_communities_name_active', table_name='communities', postgresql_where=sa.text("status <> 'rejected'"))
    op.create_index('uq_communities_name_active', 'communities', [sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text("status NOT IN ('rejected', 'blocked')"))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_communities_name_active', table_name='communities', postgresql_where=sa.text("status NOT IN ('rejected', 'blocked')"))
    op.execute("UPDATE communities SET status = 'rejected' WHERE status = 'blocked'")
    op.execute("ALTER TYPE community_status RENAME TO community_status_old")
    op.execute("CREATE TYPE community_status AS ENUM ('pending', 'published', 'rejected')")
    op.execute("ALTER TABLE communities ALTER COLUMN status TYPE community_status USING status::text::community_status")
    op.execute("DROP TYPE community_status_old")
    op.create_index('uq_communities_name_active', 'communities', [sa.literal_column('lower(name)')], unique=True, postgresql_where=sa.text("status <> 'rejected'"))
    op.drop_column('communities', 'resubmission_count')
