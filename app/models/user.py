import enum
from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.permissions import VERIFIED_ACCOUNT_ROLE_SLUGS
from app.core.timezone import app_now
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.user_has_role import UserRoleAssignment, user_has_roles
from app.utils.age import is_adult_on

if TYPE_CHECKING:
    from app.models.auth_identity import AuthIdentity
    from app.models.role import Role


class UserStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING_VERIFICATION = "pending_verification"


class UserType(enum.StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"


class UserGender(enum.StrEnum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


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
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(30))
    password_hash: Mapped[str | None] = mapped_column(String(255))
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
    gender: Mapped[UserGender | None] = mapped_column(
        Enum(
            UserGender,
            name="user_gender",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        ),
        default=None,
    )
    date_of_birth: Mapped[date | None] = mapped_column(Date, default=None)
    email_verified_at: Mapped[datetime | None] = mapped_column(default=None)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    terms_accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    account_role_selected_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)
    last_seen_at: Mapped[datetime | None] = mapped_column(default=None)
    created_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    roles: Mapped[list["Role"]] = relationship(secondary=user_has_roles, back_populates="users")
    role_assignments: Mapped[list[UserRoleAssignment]] = relationship(
        primaryjoin="User.id == foreign(UserRoleAssignment.user_id)",
        viewonly=True,
    )
    auth_identities: Mapped[list["AuthIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def approved_roles(self) -> list["Role"]:
        unverified_role_ids = {
            assignment.role_id
            for assignment in self.role_assignments
            if assignment.verified_at is None
        }
        return [
            role
            for role in self.roles
            if role.slug not in VERIFIED_ACCOUNT_ROLE_SLUGS or role.id not in unverified_role_ids
        ]

    @property
    def is_adult(self) -> bool | None:
        if self.date_of_birth is None:
            return None
        return is_adult_on(self.date_of_birth, app_now().date())

    @property
    def linked_providers(self) -> list[str]:
        return sorted(identity.provider.value for identity in self.auth_identities)
