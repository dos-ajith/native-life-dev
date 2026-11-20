"""add platform fee snapshots and earnings ledger

Revision ID: a6c3e9f1b250
Revises: f2b8d4c6a917
Create Date: 2026-11-19 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a6c3e9f1b250"
down_revision: str | Sequence[str] | None = "f2b8d4c6a917"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BENEFICIARY = sa.Enum(
    "business", "individual_seller", "promoter", "platform", name="earning_beneficiary"
)
SOURCE = sa.Enum("order", "booking", name="earning_source")
PAYMENT_MODE = sa.Enum("online", "cash", name="earning_payment_mode")
STATUS = sa.Enum("pending", "available", "reversed", name="earning_status")


def upgrade() -> None:
    """Upgrade schema."""
    for table, amount_precision in (("orders", 14), ("bookings", 12)):
        op.add_column(
            table,
            sa.Column(
                "platform_fee_percent",
                sa.Numeric(precision=5, scale=2),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "platform_fee_amount",
                sa.Numeric(precision=amount_precision, scale=2),
                server_default=sa.text("0"),
                nullable=False,
            ),
        )
    op.create_table(
        "earnings",
        sa.Column("beneficiary_type", BENEFICIARY, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("source_type", SOURCE, nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("reference_number", sa.String(length=40), nullable=False),
        sa.Column("gross_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("platform_fee_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("net_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("payment_mode", PAYMENT_MODE, nullable=False),
        sa.Column("status", STATUS, nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=True),
        sa.Column("reversed_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(order_id, booking_id) = 1", name="ck_earnings_exactly_one_source"
        ),
        sa.ForeignKeyConstraint(["booking_id"], ["bookings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_id", "beneficiary_type", name="uq_earnings_booking_beneficiary"),
        sa.UniqueConstraint("order_id", "beneficiary_type", name="uq_earnings_order_beneficiary"),
    )
    op.create_index("ix_earnings_business_id", "earnings", ["business_id"])
    op.create_index("ix_earnings_user_id", "earnings", ["user_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_earnings_user_id", table_name="earnings")
    op.drop_index("ix_earnings_business_id", table_name="earnings")
    op.drop_table("earnings")
    for enum_type in (STATUS, PAYMENT_MODE, SOURCE, BENEFICIARY):
        enum_type.drop(op.get_bind(), checkfirst=True)
    for table in ("bookings", "orders"):
        op.drop_column(table, "platform_fee_amount")
        op.drop_column(table, "platform_fee_percent")
