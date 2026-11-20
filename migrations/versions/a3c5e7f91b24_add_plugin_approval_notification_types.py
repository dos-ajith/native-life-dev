"""add plugin approval notification and email types

Revision ID: a3c5e7f91b24
Revises: 1a8f013b0500
Create Date: 2026-11-17 10:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c5e7f91b24"
down_revision: str | Sequence[str] | None = "1a8f013b0500"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    statements = (
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'plugin_approval_requested'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'plugin_approval_approved'",
        "ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'plugin_approval_rejected'",
        "ALTER TYPE email_type ADD VALUE IF NOT EXISTS 'plugin_approval_requested'",
    )
    with op.get_context().autocommit_block():
        for statement in statements:
            op.execute(statement)


def downgrade() -> None:
    """Downgrade schema."""
    pass
