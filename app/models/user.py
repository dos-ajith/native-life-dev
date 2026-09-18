import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_has_role import user_has_roles

if TYPE_CHECKING:
    from app.models.role import Role


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserType(enum.StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "ix_users_email_active",
            "email",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "ix_users_phone_active",
            "phone",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )

    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str] = mapped_column(String(255))
    profile_image_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[UserStatus] = mapped_column(
        Enum(
            UserStatus,
            name="user_status",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserStatus.PENDING_VERIFICATION,
    )
    user_type: Mapped[UserType] = mapped_column(
        Enum(
            UserType,
            name="user_type",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=UserType.PUBLIC,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)

    roles: Mapped[list["Role"]] = relationship(secondary=user_has_roles, back_populates="users")
