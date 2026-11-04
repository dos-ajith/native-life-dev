"""add category approved and rejected notification types

Revision ID: e5a9c3d1f7b2
Revises: d4f2b8c7e1a3
Create Date: 2026-10-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a9c3d1f7b2'
down_revision: Union[str, Sequence[str], None] = 'd4f2b8c7e1a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'category_approved'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'category_rejected'")


def downgrade() -> None:
    """Downgrade schema."""
    pass
