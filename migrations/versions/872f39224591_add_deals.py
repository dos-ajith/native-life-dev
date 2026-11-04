"""add deals

Revision ID: 872f39224591
Revises: b538f52a014a
Create Date: 2026-10-19 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '872f39224591'
down_revision: Union[str, Sequence[str], None] = 'b538f52a014a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEAL_NOTIFICATION_TYPES = (
    'deal_acceptance_requested',
    'deal_no_eligible_acceptors',
    'deal_no_eligible_acceptors_admin',
    'deal_published',
    'deal_expired',
)


def upgrade() -> None:
    """Upgrade schema."""
    for notification_type in DEAL_NOTIFICATION_TYPES:
        op.execute(f"ALTER TYPE notification_type ADD VALUE IF NOT EXISTS '{notification_type}'")

    op.create_table('deals',
    sa.Column('created_by', sa.Uuid(), nullable=False),
    sa.Column('business_id', sa.Uuid(), nullable=True),
    sa.Column('category_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('draft', 'pending_acceptance', 'published', 'cancelled', 'expired', name='deal_status'), nullable=False),
    sa.Column('max_acceptances', sa.SmallInteger(), server_default=sa.text('1'), nullable=False),
    sa.Column('accepted_count', sa.SmallInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('valid_until', sa.DateTime(), nullable=True),
    sa.Column('submitted_at', sa.DateTime(), nullable=True),
    sa.Column('acceptance_deadline', sa.DateTime(), nullable=True),
    sa.Column('published_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('max_acceptances >= 1', name='ck_deals_max_acceptances_positive'),
    sa.CheckConstraint('accepted_count >= 0 AND accepted_count <= max_acceptances', name='ck_deals_accepted_count_within_max'),
    sa.ForeignKeyConstraint(['business_id'], ['businesses.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deals_created_by', 'deals', ['created_by'], unique=False)
    op.create_index('ix_deals_business_id', 'deals', ['business_id'], unique=False)
    op.create_index('ix_deals_category_id', 'deals', ['category_id'], unique=False)
    op.create_index(
        'ix_deals_published_at',
        'deals',
        ['published_at'],
        unique=False,
        postgresql_where=sa.text("status = 'published' AND deleted_at IS NULL"),
    )
    op.create_index(
        'ix_deals_acceptance_deadline',
        'deals',
        ['acceptance_deadline'],
        unique=False,
        postgresql_where=sa.text("status = 'pending_acceptance'"),
    )

    op.create_table('deal_natives',
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('village_id', sa.Uuid(), nullable=False),
    sa.Column('is_primary', sa.Boolean(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['village_id'], ['gis_villages.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('deal_id', 'village_id', name='uq_deal_natives_deal_id_village_id')
    )
    op.create_index(
        'uq_deal_natives_one_primary',
        'deal_natives',
        ['deal_id'],
        unique=True,
        postgresql_where=sa.text('is_primary'),
    )
    op.create_index('ix_deal_natives_village_id_deal_id', 'deal_natives', ['village_id', 'deal_id'], unique=False)

    op.create_table('deal_images',
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('storage_path', sa.String(length=1024), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('file_size_bytes', sa.Integer(), nullable=False),
    sa.Column('is_thumbnail', sa.Boolean(), nullable=False),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deal_images_deal_id', 'deal_images', ['deal_id'], unique=False)
    op.create_index(
        'uq_deal_images_one_thumbnail',
        'deal_images',
        ['deal_id'],
        unique=True,
        postgresql_where=sa.text('is_thumbnail'),
    )

    op.create_table('deal_items',
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('original_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('deal_price', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('image_id', sa.Uuid(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('quantity IS NULL OR quantity > 0', name='ck_deal_items_quantity_positive'),
    sa.CheckConstraint('original_price IS NULL OR original_price >= 0', name='ck_deal_items_original_price_non_negative'),
    sa.CheckConstraint('deal_price IS NULL OR deal_price >= 0', name='ck_deal_items_deal_price_non_negative'),
    sa.CheckConstraint('original_price IS NULL OR deal_price IS NULL OR deal_price <= original_price', name='ck_deal_items_deal_price_within_original'),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['image_id'], ['deal_images.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_deal_items_deal_id', 'deal_items', ['deal_id'], unique=False)

    op.create_table('deal_invitations',
    sa.Column('deal_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('role_id', sa.Uuid(), nullable=False),
    sa.Column('status', sa.Enum('invited', 'accepted', 'declined', 'closed', name='deal_invitation_status'), nullable=False),
    sa.Column('notified_at', sa.DateTime(), nullable=True),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['deal_id'], ['deals.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('deal_id', 'user_id', name='uq_deal_invitations_deal_id_user_id')
    )
    op.create_index('ix_deal_invitations_user_id_status', 'deal_invitations', ['user_id', 'status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_deal_invitations_user_id_status', table_name='deal_invitations')
    op.drop_table('deal_invitations')
    op.drop_index('ix_deal_items_deal_id', table_name='deal_items')
    op.drop_table('deal_items')
    op.drop_index('uq_deal_images_one_thumbnail', table_name='deal_images', postgresql_where=sa.text('is_thumbnail'))
    op.drop_index('ix_deal_images_deal_id', table_name='deal_images')
    op.drop_table('deal_images')
    op.drop_index('ix_deal_natives_village_id_deal_id', table_name='deal_natives')
    op.drop_index('uq_deal_natives_one_primary', table_name='deal_natives', postgresql_where=sa.text('is_primary'))
    op.drop_table('deal_natives')
    op.drop_index('ix_deals_acceptance_deadline', table_name='deals', postgresql_where=sa.text("status = 'pending_acceptance'"))
    op.drop_index('ix_deals_published_at', table_name='deals', postgresql_where=sa.text("status = 'published' AND deleted_at IS NULL"))
    op.drop_index('ix_deals_category_id', table_name='deals')
    op.drop_index('ix_deals_business_id', table_name='deals')
    op.drop_index('ix_deals_created_by', table_name='deals')
    op.drop_table('deals')
    op.execute('DROP TYPE deal_invitation_status')
    op.execute('DROP TYPE deal_status')
