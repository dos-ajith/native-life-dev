"""add text_body and html_body to emails

Revision ID: 3cfb448af869
Revises: 3c2ed1a58c49
Create Date: 2026-09-29 12:34:32.772461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3cfb448af869'
down_revision: Union[str, Sequence[str], None] = '3c2ed1a58c49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'emails', sa.Column('text_body', sa.Text(), nullable=False, server_default='')
    )
    op.add_column(
        'emails', sa.Column('html_body', sa.Text(), nullable=False, server_default='')
    )
    op.alter_column('emails', 'text_body', server_default=None)
    op.alter_column('emails', 'html_body', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('emails', 'html_body')
    op.drop_column('emails', 'text_body')
