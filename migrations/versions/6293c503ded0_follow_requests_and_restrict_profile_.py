"""follow requests and restrict profile visibility

Revision ID: 6293c503ded0
Revises: 692c0a5cdad6
Create Date: 2026-09-24 10:58:09.194666

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6293c503ded0'
down_revision: Union[str, Sequence[str], None] = '692c0a5cdad6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


profile_visibility_level_enum = postgresql.ENUM(
    'public', 'private', name='profile_visibility_level', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    profile_visibility_level_enum.create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE user_privacy_settings "
        "ALTER COLUMN profile_visibility TYPE profile_visibility_level "
        "USING (CASE profile_visibility::text "
        "WHEN 'followers' THEN 'private' "
        "ELSE profile_visibility::text END)::profile_visibility_level"
    )
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'follow_requested'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'follow_request_accepted'")

    op.create_table('user_follow_requests',
    sa.Column('requester_id', sa.Uuid(), nullable=False),
    sa.Column('target_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.CheckConstraint('requester_id <> target_id', name='ck_user_follow_requests_not_self'),
    sa.ForeignKeyConstraint(['requester_id'], ['users.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint(
        'requester_id', 'target_id', name='uq_user_follow_requests_requester_id_target_id'
    )
    )
    op.create_index(
        'ix_user_follow_requests_target_id', 'user_follow_requests', ['target_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_user_follow_requests_target_id', table_name='user_follow_requests')
    op.drop_table('user_follow_requests')

    op.execute(
        "ALTER TABLE user_privacy_settings "
        "ALTER COLUMN profile_visibility TYPE visibility_level "
        "USING profile_visibility::text::visibility_level"
    )
    bind = op.get_bind()
    profile_visibility_level_enum.drop(bind, checkfirst=True)
