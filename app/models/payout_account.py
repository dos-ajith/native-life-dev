from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

HOLDER_NAME_LENGTH = 150
LAST4_LENGTH = 4
IFSC_LENGTH = 11
UPI_ID_LENGTH = 100
PROVIDER_ID_LENGTH = 100


class PayoutAccount(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payout_accounts"
    __table_args__ = (
        Index(
            "uq_payout_accounts_business_id",
            "business_id",
            unique=True,
            postgresql_where=text("business_id IS NOT NULL"),
        ),
        Index(
            "uq_payout_accounts_personal_user_id",
            "user_id",
            unique=True,
            postgresql_where=text("business_id IS NULL"),
        ),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    business_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), default=None
    )
    account_holder_name: Mapped[str] = mapped_column(String(HOLDER_NAME_LENGTH))
    account_number_encrypted: Mapped[str | None] = mapped_column(Text(), default=None)
    account_number_last4: Mapped[str | None] = mapped_column(String(LAST4_LENGTH), default=None)
    ifsc: Mapped[str | None] = mapped_column(String(IFSC_LENGTH), default=None)
    upi_id: Mapped[str | None] = mapped_column(String(UPI_ID_LENGTH), default=None)
    razorpayx_contact_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_ID_LENGTH), default=None
    )
    razorpayx_fund_account_id: Mapped[str | None] = mapped_column(
        String(PROVIDER_ID_LENGTH), default=None
    )
