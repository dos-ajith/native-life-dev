from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.permission import Permission
from app.models.role_has_permission import role_has_permissions
from app.models.user_has_role import user_has_roles

if TYPE_CHECKING:
    from app.models.user import User


class Role(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "roles"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(255))

    permissions: Mapped[list[Permission]] = relationship(
        secondary=role_has_permissions, back_populates="roles"
    )
    users: Mapped[list["User"]] = relationship(secondary=user_has_roles, back_populates="roles")
