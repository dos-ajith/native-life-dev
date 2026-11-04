from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class PhoneOtpChallenge(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "phone_otp_challenges"
    __table_args__ = (
        Index("ix_phone_otp_challenges_phone_created_at", "phone", "created_at"),
        Index("ix_phone_otp_challenges_ip_address_created_at", "ip_address", "created_at"),
    )

    phone: Mapped[str] = mapped_column(String(16))
    otp_hash: Mapped[str] = mapped_column(String(255))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
