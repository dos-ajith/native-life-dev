"""add business address fields and village

Revision ID: f2b8d4c6a917
Revises: e7a3c5b9d214
Create Date: 2026-11-19 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f2b8d4c6a917"
down_revision: str | Sequence[str] | None = "e7a3c5b9d214"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("businesses", sa.Column("address_line", sa.String(length=255), nullable=True))
    op.add_column("businesses", sa.Column("landmark", sa.String(length=150), nullable=True))
    op.add_column("businesses", sa.Column("pincode", sa.String(length=6), nullable=True))
    op.add_column("businesses", sa.Column("village_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("businesses_village_id_fkey"),
        "businesses",
        "gis_villages",
        ["village_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("businesses_village_id_fkey"), "businesses", type_="foreignkey")
    op.drop_column("businesses", "village_id")
    op.drop_column("businesses", "pincode")
    op.drop_column("businesses", "landmark")
    op.drop_column("businesses", "address_line")
