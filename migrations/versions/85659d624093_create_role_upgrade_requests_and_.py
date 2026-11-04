"""create role upgrade requests and documents tables

Revision ID: 85659d624093
Revises: 3cfb448af869
Create Date: 2026-09-29 20:23:47.192184

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '85659d624093'
down_revision: Union[str, Sequence[str], None] = '3cfb448af869'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


role_upgrade_request_status_enum = postgresql.ENUM(
    'pending', 'approved', 'rejected', name='role_upgrade_request_status', create_type=False
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE email_type ADD VALUE IF NOT EXISTS 'role_upgrade_approved'")
    op.execute("ALTER TYPE email_type ADD VALUE IF NOT EXISTS 'role_upgrade_rejected'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'role_upgrade_approved'")
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'role_upgrade_rejected'")

    bind = op.get_bind()
    role_upgrade_request_status_enum.create(bind, checkfirst=True)

    op.create_table('role_upgrade_requests',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('requested_role_id', sa.Uuid(), nullable=False),
    sa.Column('status', role_upgrade_request_status_enum, nullable=False),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('reviewed_by', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(), nullable=True),
    sa.Column('review_note', sa.Text(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['requested_role_id'], ['roles.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_role_upgrade_requests_user_id', 'role_upgrade_requests', ['user_id'], unique=False
    )
    op.create_index(
        'ix_role_upgrade_requests_requested_role_id',
        'role_upgrade_requests',
        ['requested_role_id'],
        unique=False,
    )
    op.create_index(
        'uq_role_upgrade_requests_pending_user_role',
        'role_upgrade_requests',
        ['user_id', 'requested_role_id'],
        unique=True,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.create_table('role_upgrade_request_documents',
    sa.Column('request_id', sa.Uuid(), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['request_id'], ['role_upgrade_requests.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_role_upgrade_request_documents_request_id',
        'role_upgrade_request_documents',
        ['request_id'],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        'ix_role_upgrade_request_documents_request_id',
        table_name='role_upgrade_request_documents',
    )
    op.drop_table('role_upgrade_request_documents')

    op.drop_index(
        'uq_role_upgrade_requests_pending_user_role',
        table_name='role_upgrade_requests',
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.drop_index('ix_role_upgrade_requests_requested_role_id', table_name='role_upgrade_requests')
    op.drop_index('ix_role_upgrade_requests_user_id', table_name='role_upgrade_requests')
    op.drop_table('role_upgrade_requests')

    bind = op.get_bind()
    role_upgrade_request_status_enum.drop(bind, checkfirst=True)

    # Postgres cannot drop individual enum values, so the 'role_upgrade_approved' and
    # 'role_upgrade_rejected' values added to email_type and notification_type are left in
    # place on downgrade.
