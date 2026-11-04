from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Column, DateTime, ForeignKey, Table, func
from sqlalchemy.orm import Mapped, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.role import Role

user_has_roles = Table(
    "user_has_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("assigned_at", DateTime(), server_default=func.now(), nullable=False),
    Column("verified_at", DateTime(), nullable=True),
)


class UserRoleAssignment(Base):
    __table__ = user_has_roles

    user_id: Mapped[UUID]
    role_id: Mapped[UUID]
    assigned_at: Mapped[datetime]
    verified_at: Mapped[datetime | None]

    role: Mapped["Role"] = relationship(viewonly=True, lazy="joined")
