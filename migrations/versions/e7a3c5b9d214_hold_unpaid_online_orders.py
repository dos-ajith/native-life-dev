"""hold online orders and their delivery requests until payment succeeds

Revision ID: e7a3c5b9d214
Revises: d5f9b2e4a613
Create Date: 2026-11-18 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e7a3c5b9d214"
down_revision: str | Sequence[str] | None = "d5f9b2e4a613"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'awaiting_payment'")
        op.execute("ALTER TYPE delivery_request_status ADD VALUE IF NOT EXISTS 'awaiting_payment'")
    op.add_column("delivery_requests", sa.Column("held_at", sa.DateTime(), nullable=True))
    op.add_column(
        "delivery_requests",
        sa.Column("held_notify_promoter_ids", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("delivery_requests", "held_notify_promoter_ids")
    op.drop_column("delivery_requests", "held_at")
