import enum

from sqlalchemy import Enum

PAYMENT_STATUS_ENUM_NAME = "payment_status"


class PaymentStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


def payment_status_column_type() -> Enum:
    return Enum(
        PaymentStatus,
        name=PAYMENT_STATUS_ENUM_NAME,
        native_enum=True,
        values_callable=lambda enum_cls: [member.value for member in enum_cls],
    )
