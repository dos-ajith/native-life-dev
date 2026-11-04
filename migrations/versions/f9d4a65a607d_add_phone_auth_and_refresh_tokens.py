"""add phone auth and refresh tokens

Revision ID: f9d4a65a607d
Revises: b8e4d2f6a9c1
Create Date: 2026-10-09 09:50:17.169110

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f9d4a65a607d'
down_revision: Union[str, Sequence[str], None] = 'b8e4d2f6a9c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column('users', 'email', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.alter_column('users', 'password_hash', existing_type=sa.VARCHAR(length=255), nullable=True)
    op.add_column('users', sa.Column('phone_verified_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('users', sa.Column('terms_accepted_at', sa.DateTime(timezone=True), nullable=True))

    op.create_table('phone_otp_challenges',
    sa.Column('phone', sa.String(length=16), nullable=False),
    sa.Column('otp_hash', sa.String(length=255), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_phone_otp_challenges_phone_created_at', 'phone_otp_challenges', ['phone', 'created_at'], unique=False)
    op.create_index('ix_phone_otp_challenges_ip_address_created_at', 'phone_otp_challenges', ['ip_address', 'created_at'], unique=False)

    op.create_table('refresh_tokens',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('access_token_jti', sa.Uuid(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_refresh_tokens_token_hash', 'refresh_tokens', ['token_hash'], unique=True)
    op.create_index('ix_refresh_tokens_access_token_jti', 'refresh_tokens', ['access_token_jti'], unique=False)
    op.create_index('ix_refresh_tokens_user_id', 'refresh_tokens', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    blocking = op.get_bind().scalar(
        sa.text("SELECT count(*) FROM users WHERE email IS NULL OR password_hash IS NULL")
    )
    if blocking:
        raise RuntimeError(
            f"Refusing to downgrade: {blocking} user(s) have no email or password "
            "(phone or Google accounts) and would violate NOT NULL"
        )
    op.drop_index('ix_refresh_tokens_user_id', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_access_token_jti', table_name='refresh_tokens')
    op.drop_index('ix_refresh_tokens_token_hash', table_name='refresh_tokens')
    op.drop_table('refresh_tokens')
    op.drop_index('ix_phone_otp_challenges_ip_address_created_at', table_name='phone_otp_challenges')
    op.drop_index('ix_phone_otp_challenges_phone_created_at', table_name='phone_otp_challenges')
    op.drop_table('phone_otp_challenges')
    op.drop_column('users', 'terms_accepted_at')
    op.drop_column('users', 'phone_verified_at')
    op.alter_column('users', 'password_hash', existing_type=sa.VARCHAR(length=255), nullable=False)
    op.alter_column('users', 'email', existing_type=sa.VARCHAR(length=255), nullable=False)
