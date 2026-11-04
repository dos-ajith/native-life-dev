"""allow two aadhaar files

Revision ID: cc467734a535
Revises: 872f39224591
Create Date: 2026-10-19 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cc467734a535'
down_revision: Union[str, Sequence[str], None] = '872f39224591'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'user_aadhaar_documents',
        sa.Column('position', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    )
    op.alter_column('user_aadhaar_documents', 'position', server_default=None)
    op.drop_constraint('uq_user_aadhaar_documents_user_id', 'user_aadhaar_documents', type_='unique')
    op.create_unique_constraint(
        'uq_user_aadhaar_documents_user_id_position',
        'user_aadhaar_documents',
        ['user_id', 'position'],
    )
    op.create_check_constraint(
        'ck_user_aadhaar_documents_position_range',
        'user_aadhaar_documents',
        'position >= 0 AND position < 2',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute('DELETE FROM user_aadhaar_documents WHERE position > 0')
    op.drop_constraint('ck_user_aadhaar_documents_position_range', 'user_aadhaar_documents', type_='check')
    op.drop_constraint('uq_user_aadhaar_documents_user_id_position', 'user_aadhaar_documents', type_='unique')
    op.create_unique_constraint('uq_user_aadhaar_documents_user_id', 'user_aadhaar_documents', ['user_id'])
    op.drop_column('user_aadhaar_documents', 'position')
