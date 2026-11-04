import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection

CATEGORIES = sa.table(
    "plg_ecommerce_product_categories",
    sa.column("id", sa.Uuid()),
    sa.column("business_id", sa.Uuid()),
    sa.column("name", sa.String()),
    sa.column("slug", sa.String()),
    sa.column("is_active", sa.Boolean()),
)
DEFAULT_CATEGORIES = (
    ("Apparel", "apparel"),
    ("Footwear", "footwear"),
    ("Electronics", "electronics"),
    ("Home & Kitchen", "home-kitchen"),
    ("Groceries", "groceries"),
    ("Beauty & Personal Care", "beauty-personal-care"),
    ("Books & Stationery", "books-stationery"),
    ("Toys & Games", "toys-games"),
    ("Health & Wellness", "health-wellness"),
    ("Other", "other"),
)


def seed(connection: Connection) -> None:
    existing: set[str] = set(
        connection.execute(
            sa.select(CATEGORIES.c.slug).where(CATEGORIES.c.business_id.is_(None))
        ).scalars()
    )
    rows = [
        {"id": uuid.uuid4(), "business_id": None, "name": name, "slug": slug, "is_active": True}
        for name, slug in DEFAULT_CATEGORIES
        if slug not in existing
    ]
    if rows:
        connection.execute(insert(CATEGORIES).values(rows).on_conflict_do_nothing())
