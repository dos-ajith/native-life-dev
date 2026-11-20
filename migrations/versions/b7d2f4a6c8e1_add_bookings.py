"""add bookings and booking notification types

Revision ID: b7d2f4a6c8e1
Revises: a3c5e7f91b24
Create Date: 2026-11-17 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b7d2f4a6c8e1"
down_revision: str | Sequence[str] | None = "a3c5e7f91b24"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

booking_status = postgresql.ENUM(
    "requested",
    "confirmed",
    "rejected",
    "cancelled",
    "completed",
    name="booking_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    booking_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("booking_number", sa.String(20), nullable=False),
        sa.Column(
            "business_id",
            sa.Uuid(),
            sa.ForeignKey("businesses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "customer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("plugin_key", sa.String(64), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        sa.Column("item_name", sa.String(200), nullable=False),
        sa.Column("status", booking_status, nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("customer_name", sa.String(150), nullable=False),
        sa.Column("customer_phone", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("original_price", sa.Numeric(12, 2), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("response_note", sa.String(500), nullable=True),
        sa.Column(
            "responded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("booking_number", name="uq_bookings_booking_number"),
        sa.CheckConstraint("party_size >= 1", name="ck_bookings_party_size_positive"),
        sa.CheckConstraint(
            "end_date IS NULL OR end_date >= start_date", name="ck_bookings_end_not_before_start"
        ),
    )
    op.create_index("ix_bookings_business_id_status", "bookings", ["business_id", "status"])
    op.create_index("ix_bookings_customer_id", "bookings", ["customer_id"])

    statements = (
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_requested'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_confirmed'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_rejected'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_cancelled'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_completed'",
        "ALTER TYPE email_type ADD VALUE IF NOT EXISTS 'booking_requested'",
    )
    with op.get_context().autocommit_block():
        for statement in statements:
            op.execute(statement)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_bookings_customer_id", table_name="bookings")
    op.drop_index("ix_bookings_business_id_status", table_name="bookings")
    op.drop_table("bookings")
    booking_status.drop(op.get_bind(), checkfirst=True)
