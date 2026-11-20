"""add online order payments and share the payment status enum

Revision ID: d5f9b2e4a613
Revises: c4e8a1d3f592
Create Date: 2026-11-18 15:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d5f9b2e4a613"
down_revision: str | Sequence[str] | None = "c4e8a1d3f592"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

payment_status = postgresql.ENUM(name="payment_status", create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE booking_payment_status RENAME TO payment_status")
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE payment_method ADD VALUE IF NOT EXISTS 'online'")
    op.create_table(
        "order_payments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Uuid(),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_link_id", sa.String(64), nullable=False, unique=True),
        sa.Column("payment_url", sa.String(500), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", payment_status, nullable=False),
        sa.Column("provider_payment_id", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("order_payments")
    op.execute("ALTER TYPE payment_status RENAME TO booking_payment_status")
