import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Enum, ForeignKey, Index, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.role import Role
    from app.models.role_upgrade_request_document import RoleUpgradeRequestDocument
    from app.models.user import User


class RoleUpgradeRequestStatus(enum.StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class RoleUpgradeRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "role_upgrade_requests"
    __table_args__ = (
        Index("ix_role_upgrade_requests_user_id", "user_id"),
        Index("ix_role_upgrade_requests_requested_role_id", "requested_role_id"),
        Index(
            "uq_role_upgrade_requests_pending_user_role",
            "user_id",
            "requested_role_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    requested_role_id: Mapped[UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    status: Mapped[RoleUpgradeRequestStatus] = mapped_column(
        Enum(
            RoleUpgradeRequestStatus,
            name="role_upgrade_request_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=RoleUpgradeRequestStatus.PENDING,
    )
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review_note: Mapped[str | None] = mapped_column(Text())

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    requested_role: Mapped["Role"] = relationship(foreign_keys=[requested_role_id])
    documents: Mapped[list["RoleUpgradeRequestDocument"]] = relationship(
        back_populates="request", cascade="all, delete-orphan"
    )
