from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Integer, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

MAX_AADHAAR_FILES = 2


class UserAadhaarDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "user_aadhaar_documents"
    __table_args__ = (
        UniqueConstraint("user_id", "position", name="uq_user_aadhaar_documents_user_id_position"),
        CheckConstraint(
            f"position >= 0 AND position < {MAX_AADHAAR_FILES}",
            name="ck_user_aadhaar_documents_position_range",
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(SmallInteger())
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer())
    storage_path: Mapped[str] = mapped_column(String(1024))
