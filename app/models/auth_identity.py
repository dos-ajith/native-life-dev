import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.user import User


class AuthProvider(enum.StrEnum):
    GOOGLE = "google"


class AuthIdentity(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "auth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "subject", name="uq_auth_identities_provider_subject"),
        UniqueConstraint("user_id", "provider", name="uq_auth_identities_user_id_provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[AuthProvider] = mapped_column(
        Enum(
            AuthProvider,
            name="auth_provider",
            native_enum=True,
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
        )
    )
    subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))

    user: Mapped["User"] = relationship(back_populates="auth_identities")
