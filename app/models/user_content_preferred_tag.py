from sqlalchemy import Column, DateTime, ForeignKey, Table, func

from app.models.base import Base

user_content_preferred_tags = Table(
    "user_content_preferred_tags",
    Base.metadata,
    Column(
        "user_content_settings_id",
        ForeignKey("user_content_settings.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    Column("created_at", DateTime(), server_default=func.now(), nullable=False),
)
