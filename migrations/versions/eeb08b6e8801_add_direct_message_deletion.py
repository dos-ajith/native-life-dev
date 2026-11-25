"""add direct message deletion

Revision ID: eeb08b6e8801
Revises: d4a7e2c91f05
Create Date: 2026-11-25 15:14:38.303378

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eeb08b6e8801"
down_revision: str | Sequence[str] | None = "d4a7e2c91f05"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("direct_messages", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    op.create_table(
        "hidden_direct_messages",
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["direct_messages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "message_id", "user_id", name="uq_hidden_direct_messages_message_id_user_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("hidden_direct_messages")
    op.drop_column("direct_messages", "deleted_at")
