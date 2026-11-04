"""create deal orders

Revision ID: e4b8d2f6a913
Revises: c7e3a91d5b24
Create Date: 2026-10-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e4b8d2f6a913"
down_revision: Union[str, Sequence[str], None] = "c7e3a91d5b24"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "deal_orders",
        sa.Column("order_number", sa.String(length=40), nullable=False),
        sa.Column("deal_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "shipped",
                "delivered",
                "cancelled",
                name="deal_order_status",
            ),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(length=150), nullable=False),
        sa.Column("customer_phone", sa.String(length=30), nullable=True),
        sa.Column("shipping_address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["customer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_number"),
    )
    op.create_index("ix_deal_orders_business_id", "deal_orders", ["business_id"], unique=False)
    op.create_index("ix_deal_orders_customer_id", "deal_orders", ["customer_id"], unique=False)
    op.create_table(
        "deal_order_items",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("deal_item_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("product_name", sa.String(length=255), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deal_item_id"], ["deal_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["deal_orders.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_deal_order_items_deal_item_id", "deal_order_items", ["deal_item_id"], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_deal_order_items_deal_item_id", table_name="deal_order_items")
    op.drop_table("deal_order_items")
    op.drop_index("ix_deal_orders_customer_id", table_name="deal_orders")
    op.drop_index("ix_deal_orders_business_id", table_name="deal_orders")
    op.drop_table("deal_orders")
    sa.Enum(name="deal_order_status").drop(op.get_bind(), checkfirst=False)
