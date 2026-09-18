from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Setting(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(150), unique=True)
    value: Mapped[str | None] = mapped_column(Text())
