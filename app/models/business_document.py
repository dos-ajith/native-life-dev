import enum
from datetime import datetime
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BusinessDocumentStatus(enum.StrEnum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class BusinessDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "business_documents"
    __table_args__ = (Index("ix_business_documents_business_id", "business_id"),)

    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="CASCADE"))
    document_type: Mapped[str] = mapped_column(String(100))
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer())
    storage_path: Mapped[str] = mapped_column(String(1024))
    status: Mapped[BusinessDocumentStatus] = mapped_column(
        Enum(
            BusinessDocumentStatus,
            name="business_document_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=BusinessDocumentStatus.PENDING,
    )
    verified_at: Mapped[datetime | None] = mapped_column(default=None)
