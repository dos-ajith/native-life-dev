"""add created_by to users

Revision ID: 527c61140770
Revises: 13e6fd5324e7
Create Date: 2026-09-21 10:15:48.625773

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '527c61140770'
down_revision: Union[str, Sequence[str], None] = '13e6fd5324e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('created_by', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f('users_created_by_fkey'), 'users', 'users', ['created_by'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_users_created_by', 'users', ['created_by'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_users_created_by', table_name='users')
    op.drop_constraint(op.f('users_created_by_fkey'), 'users', type_='foreignkey')
    op.drop_column('users', 'created_by')
