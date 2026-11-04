"""add gender and date of birth to users

Revision ID: 43b997b1e15c
Revises: 5c5c2fb4090a
Create Date: 2026-10-12 10:54:01.366266

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '43b997b1e15c'
down_revision: Union[str, Sequence[str], None] = '5c5c2fb4090a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


GENDER_ENUM = 'user_gender'


def upgrade() -> None:
    """Upgrade schema."""
    gender = sa.Enum('male', 'female', 'other', name=GENDER_ENUM)
    gender.create(op.get_bind(), checkfirst=True)
    op.add_column('users', sa.Column('gender', gender, nullable=True))
    op.add_column('users', sa.Column('date_of_birth', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'date_of_birth')
    op.drop_column('users', 'gender')
    sa.Enum(name=GENDER_ENUM).drop(op.get_bind(), checkfirst=True)
