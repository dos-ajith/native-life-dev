"""add post comment likes

Revision ID: d4a7e2c91f05
Revises: c9e5a3b8d472
Create Date: 2026-11-24 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a7e2c91f05"
down_revision: str | Sequence[str] | None = "c9e5a3b8d472"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE notification_type ADD VALUE IF NOT EXISTS 'comment_liked'")
    op.add_column(
        "post_comments",
        sa.Column("likes_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_table(
        "post_comment_likes",
        sa.Column("comment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["comment_id"], ["post_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "comment_id", "user_id", name="uq_post_comment_likes_comment_id_user_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("post_comment_likes")
    op.drop_column("post_comments", "likes_count")
