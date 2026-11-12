from decimal import ROUND_HALF_UP, Decimal

PERCENT_DIVISOR = Decimal(100)
MONEY_QUANTUM = Decimal("0.01")


def tax_for(line_total: Decimal, tax_percent: Decimal) -> Decimal:
    return (line_total * tax_percent / PERCENT_DIVISOR).quantize(
        MONEY_QUANTUM, rounding=ROUND_HALF_UP
    )
