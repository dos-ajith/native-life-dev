from sqlalchemy import Column, ForeignKey, Table

from app.models.base import Base

user_has_roles = Table(
    "user_has_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)
