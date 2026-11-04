"""add auth identities

Revision ID: a3c7e9b1d204
Revises: f9d4a65a607d
Create Date: 2026-10-09 10:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7e9b1d204'
down_revision: Union[str, Sequence[str], None] = 'f9d4a65a607d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('auth_identities',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('provider', sa.Enum('google', name='auth_provider'), nullable=False),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'subject', name='uq_auth_identities_provider_subject'),
    sa.UniqueConstraint('user_id', 'provider', name='uq_auth_identities_user_id_provider')
    )


def downgrade() -> None:
    """Downgrade schema."""
    blocking = op.get_bind().scalar(
        sa.text(
            "SELECT count(*) FROM users u JOIN auth_identities i ON i.user_id = u.id "
            "WHERE u.password_hash IS NULL AND u.phone_verified_at IS NULL"
        )
    )
    if blocking:
        raise RuntimeError(
            f"Refusing to downgrade: {blocking} user(s) can only sign in with Google"
        )
    op.drop_table('auth_identities')
    sa.Enum(name='auth_provider').drop(op.get_bind(), checkfirst=True)
