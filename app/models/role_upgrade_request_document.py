from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role_upgrade_request import RoleUpgradeRequest


class RoleUpgradeRequestDocument(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "role_upgrade_request_documents"
    __table_args__ = (Index("ix_role_upgrade_request_documents_request_id", "request_id"),)

    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("role_upgrade_requests.id", ondelete="CASCADE")
    )
    file_name: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int] = mapped_column(Integer())
    storage_path: Mapped[str] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    request: Mapped["RoleUpgradeRequest"] = relationship(back_populates="documents")
