from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import ORDER_NUMBER_SEQUENCE
from app.services.deal_expiry_service import deal_clock_now

ORDER_NUMBER_PREFIX = "NL"
ORDER_NUMBER_WIDTH = 6


def new_order_number(db: Session) -> str:
    sequence_value = db.scalar(select(ORDER_NUMBER_SEQUENCE.next_value()))
    return f"{ORDER_NUMBER_PREFIX}{deal_clock_now():%y}{sequence_value:0{ORDER_NUMBER_WIDTH}d}"
