"""rename user_type enum values to public and private

Revision ID: 65cdfca8f2e9
Revises: 69a165a4120c
Create Date: 2026-09-17 13:40:11.790987

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '65cdfca8f2e9'
down_revision: Union[str, Sequence[str], None] = '69a165a4120c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE user_type RENAME VALUE 'customer' TO 'public'")
    op.execute("ALTER TYPE user_type RENAME VALUE 'admin' TO 'private'")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TYPE user_type RENAME VALUE 'private' TO 'admin'")
    op.execute("ALTER TYPE user_type RENAME VALUE 'public' TO 'customer'")
