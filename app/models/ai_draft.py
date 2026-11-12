import enum
from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

AI_DRAFT_KIND_MAX_LENGTH = 50


class AIDraftKind(enum.StrEnum):
    DEAL = "deal"


class AIDraft(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ai_drafts"
    __table_args__ = (UniqueConstraint("user_id", "kind"),)

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(AI_DRAFT_KIND_MAX_LENGTH))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB())
