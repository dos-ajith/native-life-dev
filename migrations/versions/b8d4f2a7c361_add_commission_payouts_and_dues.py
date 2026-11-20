"""add commission, gateway charge, payouts, payout accounts and COD dues

Revision ID: b8d4f2a7c361
Revises: a6c3e9f1b250
Create Date: 2026-11-19 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "b8d4f2a7c361"
down_revision: str | Sequence[str] | None = "a6c3e9f1b250"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DUES_STATUS = sa.Enum("owed", "paid", "offset", name="earning_dues_status")
PAYEE_TYPE = sa.Enum("business", "individual_seller", "promoter", "native_admin", name="payee_type")
PAYOUT_STATUS = sa.Enum("draft", "processing", "paid", "failed", "cancelled", name="payout_status")
PAYOUT_METHOD = sa.Enum("manual", "razorpayx", name="payout_method")
PAYMENT_STATUS = postgresql.ENUM(name="payment_status", create_type=False)
NEW_ENUM_VALUES = (
    ("earning_beneficiary", "promoter_commission"),
    ("earning_beneficiary", "native_admin"),
    ("earning_status", "settled"),
    ("notification_type", "cod_dues_owed"),
    ("notification_type", "dues_statement"),
    ("notification_type", "dues_paid"),
    ("notification_type", "payout_paid"),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    ]


def _money(name: str, precision: int = 14) -> sa.Column:
    return sa.Column(
        name,
        sa.Numeric(precision=precision, scale=2),
        server_default=sa.text("0"),
        nullable=False,
    )


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        for enum_name, value in NEW_ENUM_VALUES:
            op.execute(f"ALTER TYPE {enum_name} ADD VALUE IF NOT EXISTS '{value}'")
    for table, precision in (("orders", 14), ("bookings", 12)):
        op.add_column(table, _money("commission_percent", 5))
        op.add_column(table, _money("commission_amount", precision))
        op.add_column(table, _money("gateway_charge_percent", 5))
    op.execute(sa.schema.CreateSequence(sa.Sequence("payout_number_seq", start=1001)))
    op.create_table(
        "payouts",
        sa.Column("payout_number", sa.String(length=20), nullable=False),
        sa.Column("payee_type", PAYEE_TYPE, nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("earnings_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("dues_offset_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("payout_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", PAYOUT_STATUS, nullable=False),
        sa.Column("method", PAYOUT_METHOD, nullable=True),
        sa.Column("payment_reference", sa.String(length=100), nullable=True),
        sa.Column("provider_payout_id", sa.String(length=100), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("paid_by", sa.Uuid(), nullable=True),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["paid_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payout_number"),
        sa.UniqueConstraint("provider_payout_id"),
    )
    op.create_index("ix_payouts_user_id", "payouts", ["user_id"])
    op.create_index("ix_payouts_business_id", "payouts", ["business_id"])
    op.create_table(
        "dues_payments",
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("provider_link_id", sa.String(length=64), nullable=False),
        sa.Column("payment_url", sa.String(length=500), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", PAYMENT_STATUS, nullable=False),
        sa.Column("provider_payment_id", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_link_id"),
    )
    op.create_index("ix_dues_payments_user_id", "dues_payments", ["user_id"])
    op.create_index("ix_dues_payments_business_id", "dues_payments", ["business_id"])
    op.create_table(
        "payout_accounts",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=True),
        sa.Column("account_holder_name", sa.String(length=150), nullable=False),
        sa.Column("account_number_encrypted", sa.Text(), nullable=True),
        sa.Column("account_number_last4", sa.String(length=4), nullable=True),
        sa.Column("ifsc", sa.String(length=11), nullable=True),
        sa.Column("upi_id", sa.String(length=100), nullable=True),
        sa.Column("razorpayx_contact_id", sa.String(length=100), nullable=True),
        sa.Column("razorpayx_fund_account_id", sa.String(length=100), nullable=True),
        *_timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_payout_accounts_business_id",
        "payout_accounts",
        ["business_id"],
        unique=True,
        postgresql_where=sa.text("business_id IS NOT NULL"),
    )
    op.create_index(
        "uq_payout_accounts_personal_user_id",
        "payout_accounts",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("business_id IS NULL"),
    )
    op.add_column("earnings", _money("commission_amount"))
    op.add_column("earnings", _money("gateway_charge_amount"))
    op.add_column("earnings", _money("dues_amount"))
    DUES_STATUS.create(op.get_bind(), checkfirst=True)
    op.add_column("earnings", sa.Column("dues_status", DUES_STATUS, nullable=True))
    op.add_column("earnings", sa.Column("payout_id", sa.Uuid(), nullable=True))
    op.add_column("earnings", sa.Column("dues_payment_id", sa.Uuid(), nullable=True))
    op.add_column("earnings", sa.Column("settled_at", sa.DateTime(), nullable=True))
    op.create_foreign_key(
        op.f("earnings_payout_id_fkey"),
        "earnings",
        "payouts",
        ["payout_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("earnings_dues_payment_id_fkey"),
        "earnings",
        "dues_payments",
        ["dues_payment_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_earnings_payout_id", "earnings", ["payout_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_earnings_payout_id", table_name="earnings")
    op.drop_constraint(op.f("earnings_dues_payment_id_fkey"), "earnings", type_="foreignkey")
    op.drop_constraint(op.f("earnings_payout_id_fkey"), "earnings", type_="foreignkey")
    for column in (
        "settled_at",
        "dues_payment_id",
        "payout_id",
        "dues_status",
        "dues_amount",
        "gateway_charge_amount",
        "commission_amount",
    ):
        op.drop_column("earnings", column)
    op.drop_table("payout_accounts")
    op.drop_table("dues_payments")
    op.drop_table("payouts")
    op.execute(sa.schema.DropSequence(sa.Sequence("payout_number_seq")))
    for enum_type in (DUES_STATUS, PAYOUT_METHOD, PAYOUT_STATUS, PAYEE_TYPE):
        enum_type.drop(op.get_bind(), checkfirst=True)
    for table in ("bookings", "orders"):
        op.drop_column(table, "gateway_charge_percent")
        op.drop_column(table, "commission_amount")
        op.drop_column(table, "commission_percent")
