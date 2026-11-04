from enum import StrEnum


class StockReason(StrEnum):
    INITIAL = "initial"
    ADJUSTMENT = "adjustment"
    RESTOCK = "restock"
    CORRECTION = "correction"
    DAMAGE = "damage"
    RETURN = "return"
    OTHER = "other"
    ORDER_CREATED = "order_created"
    ORDER_CANCELLED = "order_cancelled"
