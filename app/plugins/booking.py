from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class BookableItem:
    id: UUID
    name: str
    price: Decimal
    currency: str
    is_active: bool
    original_price: Decimal | None = None
    tax_percent: Decimal = Decimal(0)


class BookingProvider(ABC):
    @abstractmethod
    def find_bookable(
        self, db: Session, business_id: UUID, item_id: UUID
    ) -> BookableItem | None: ...
