"""add booking tax and booking payments

Revision ID: c4e8a1d3f592
Revises: b7d2f4a6c8e1
Create Date: 2026-11-18 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4e8a1d3f592"
down_revision: str | Sequence[str] | None = "b7d2f4a6c8e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

booking_payment_status = postgresql.ENUM(
    "pending",
    "paid",
    "expired",
    "cancelled",
    name="booking_payment_status",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bookings",
        sa.Column("tax_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
    )
    booking_payment_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "booking_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "booking_id",
            sa.Uuid(),
            sa.ForeignKey("bookings.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_link_id", sa.String(64), nullable=False, unique=True),
        sa.Column("payment_url", sa.String(500), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("tax_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("tax_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", booking_payment_status, nullable=False),
        sa.Column("provider_payment_id", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'booking_paid'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("booking_payments")
    booking_payment_status.drop(op.get_bind(), checkfirst=True)
    op.drop_column("bookings", "tax_percent")
