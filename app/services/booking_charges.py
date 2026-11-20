from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.models.booking import Booking

MONEY_STEP = Decimal("0.01")
PERCENT = Decimal(100)


@dataclass(frozen=True)
class BookingCharges:
    unit_price: Decimal
    party_size: int
    subtotal: Decimal
    tax_percent: Decimal
    tax_amount: Decimal
    total_amount: Decimal


def booking_charges(booking: Booking) -> BookingCharges:
    subtotal = (booking.unit_price * booking.party_size).quantize(MONEY_STEP, ROUND_HALF_UP)
    tax_amount = (subtotal * booking.tax_percent / PERCENT).quantize(MONEY_STEP, ROUND_HALF_UP)
    return BookingCharges(
        unit_price=booking.unit_price,
        party_size=booking.party_size,
        subtotal=subtotal,
        tax_percent=booking.tax_percent,
        tax_amount=tax_amount,
        total_amount=subtotal + tax_amount,
    )
