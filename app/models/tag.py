from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Tag(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tags"

    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
