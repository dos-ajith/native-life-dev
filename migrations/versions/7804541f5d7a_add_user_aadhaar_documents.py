"""add user aadhaar documents

Revision ID: 7804541f5d7a
Revises: f9c6e4a1b8d3
Create Date: 2026-10-15 21:28:33.180408

One Aadhaar document per user: uploading again replaces the row, so user_id
is unique.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7804541f5d7a'
down_revision: Union[str, Sequence[str], None] = 'f9c6e4a1b8d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('user_aadhaar_documents',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_user_aadhaar_documents_user_id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('user_aadhaar_documents')
