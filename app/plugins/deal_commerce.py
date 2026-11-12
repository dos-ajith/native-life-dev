from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DealProduct:
    id: UUID
    name: str
    description: str | None
    unit: str | None
    selling_price: Decimal
    is_active: bool
    tax_percent: Decimal = Decimal(0)


@dataclass(frozen=True)
class StockLine:
    product_id: UUID
    quantity: int


class DealCommerceProvider(ABC):
    @abstractmethod
    def find_products(
        self, db: Session, business_id: UUID, product_ids: Sequence[UUID]
    ) -> dict[UUID, DealProduct]: ...

    @abstractmethod
    def currency(self, db: Session, business_id: UUID) -> str: ...

    @abstractmethod
    def reserve_stock(
        self,
        db: Session,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None: ...

    @abstractmethod
    def release_stock(
        self,
        db: Session,
        business_id: UUID,
        order_id: UUID,
        lines: Sequence[StockLine],
        actor_id: UUID,
    ) -> None: ...
