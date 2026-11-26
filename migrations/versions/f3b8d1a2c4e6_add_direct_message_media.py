"""add direct message media

Revision ID: f3b8d1a2c4e6
Revises: eeb08b6e8801
Create Date: 2026-11-26 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "f3b8d1a2c4e6"
down_revision: str | Sequence[str] | None = "eeb08b6e8801"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

direct_message_media_type = postgresql.ENUM(
    "image", "video", name="direct_message_media_type", create_type=False
)


def upgrade() -> None:
    direct_message_media_type.create(op.get_bind(), checkfirst=False)
    op.add_column(
        "direct_messages", sa.Column("media_type", direct_message_media_type, nullable=True)
    )
    op.add_column(
        "direct_messages", sa.Column("media_storage_path", sa.String(length=1024), nullable=True)
    )
    op.add_column(
        "direct_messages", sa.Column("media_content_type", sa.String(length=100), nullable=True)
    )
    op.add_column("direct_messages", sa.Column("media_size_bytes", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("direct_messages", "media_size_bytes")
    op.drop_column("direct_messages", "media_content_type")
    op.drop_column("direct_messages", "media_storage_path")
    op.drop_column("direct_messages", "media_type")
    direct_message_media_type.drop(op.get_bind(), checkfirst=False)
