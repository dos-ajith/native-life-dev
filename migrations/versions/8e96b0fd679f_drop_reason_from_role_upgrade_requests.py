"""drop reason from role upgrade requests

Revision ID: 8e96b0fd679f
Revises: 85659d624093
Create Date: 2026-10-01 14:25:21.247739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8e96b0fd679f'
down_revision: Union[str, Sequence[str], None] = '85659d624093'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('role_upgrade_requests', 'reason')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('role_upgrade_requests', sa.Column('reason', sa.Text(), nullable=True))
