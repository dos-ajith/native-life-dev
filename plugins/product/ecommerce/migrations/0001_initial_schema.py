from typing import Any

import sqlalchemy as sa
from alembic.operations import Operations

PREFIX = "plg_ecommerce_"
NOW = sa.text("now()")


def _timestamps() -> list[sa.Column[Any]]:
    return [
        sa.Column("created_at", sa.DateTime(), server_default=NOW, nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=NOW, nullable=False),
    ]


def _business_fk(ondelete: str) -> sa.ForeignKey:
    return sa.ForeignKey("businesses.id", ondelete=ondelete)


def _user_fk() -> sa.ForeignKey:
    return sa.ForeignKey("users.id", ondelete="SET NULL")


def upgrade(op: Operations) -> None:
    op.create_table(
        f"{PREFIX}product_categories",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), _business_fk("CASCADE"), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        *_timestamps(),
    )
    op.create_index(
        f"uq_{PREFIX}categories_business_slug",
        f"{PREFIX}product_categories",
        ["business_id", "slug"],
        unique=True,
        postgresql_where=sa.text("business_id IS NOT NULL"),
    )
    op.create_index(
        f"uq_{PREFIX}categories_global_slug",
        f"{PREFIX}product_categories",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("business_id IS NULL"),
    )

    op.create_table(
        f"{PREFIX}products",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), _business_fk("CASCADE"), nullable=False),
        sa.Column(
            "category_id",
            sa.Uuid(),
            sa.ForeignKey(f"{PREFIX}product_categories.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("selling_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("original_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_bulk_promotable", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "is_individually_promotable", sa.Boolean(), server_default=sa.false(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), _user_fk(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("business_id", "sku", name=f"uq_{PREFIX}products_business_sku"),
    )

    op.create_table(
        f"{PREFIX}product_images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey(f"{PREFIX}products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.String(500), nullable=False),
        sa.Column("alt_text", sa.String(200), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_type", sa.String(50), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        f"ix_{PREFIX}product_images_product_id", f"{PREFIX}product_images", ["product_id"]
    )

    op.create_table(
        f"{PREFIX}stock_levels",
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey(f"{PREFIX}products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("business_id", sa.Uuid(), _business_fk("CASCADE"), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("low_stock_threshold", sa.Integer(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("quantity >= 0", name=f"ck_{PREFIX}stock_levels_quantity_not_negative"),
    )
    op.create_index(
        f"ix_{PREFIX}stock_levels_business_id", f"{PREFIX}stock_levels", ["business_id"]
    )

    op.create_table(
        f"{PREFIX}stock_movements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("business_id", sa.Uuid(), _business_fk("CASCADE"), nullable=False),
        sa.Column(
            "product_id",
            sa.Uuid(),
            sa.ForeignKey(f"{PREFIX}products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("change", sa.Integer(), nullable=False),
        sa.Column("quantity_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(30), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("created_by", sa.Uuid(), _user_fk(), nullable=True),
        *_timestamps(),
    )
    op.create_index(
        f"ix_{PREFIX}stock_movements_product_created",
        f"{PREFIX}stock_movements",
        ["product_id", "created_at"],
    )

    op.create_table(
        f"{PREFIX}settings",
        sa.Column("business_id", sa.Uuid(), _business_fk("CASCADE"), primary_key=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("default_low_stock_threshold", sa.Integer(), nullable=False),
        *_timestamps(),
    )
