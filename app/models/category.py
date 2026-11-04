import enum
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Enum, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class CategoryStatus(enum.StrEnum):
    PENDING = "pending"
    PUBLISHED = "published"
    REJECTED = "rejected"


class Category(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        Index(
            "uq_categories_parent_id_name",
            "parent_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL AND status <> 'rejected'"),
        ),
        Index(
            "uq_categories_root_name",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("parent_id IS NULL AND status <> 'rejected'"),
        ),
    )

    parent_id: Mapped[UUID | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean(), server_default=text("true"), default=True)
    sort_order: Mapped[int] = mapped_column(Integer(), server_default=text("0"), default=0)
    status: Mapped[CategoryStatus] = mapped_column(
        Enum(
            CategoryStatus,
            name="category_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=CategoryStatus.PENDING,
    )
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(default=None)
    review_note: Mapped[str | None] = mapped_column(Text())

    parent: Mapped["Category | None"] = relationship(remote_side="Category.id")
    submitter: Mapped["User | None"] = relationship(foreign_keys=[created_by])
