from app.core.exceptions import BusinessRuleError, ConflictError
from app.core.messages import DealMessages
from app.models.deal import Deal, DealStatus
from app.services.deal_expiry_service import deal_clock_now


def ensure_deal_open(deal: Deal) -> None:
    if deal.status == DealStatus.CLOSED:
        raise ConflictError(DealMessages.DEAL_CLOSED)
    if deal.status != DealStatus.PUBLISHED:
        raise ConflictError(DealMessages.NOT_PUBLISHED)
    now = deal_clock_now()
    if deal.starts_at is not None and deal.starts_at > now:
        raise BusinessRuleError(DealMessages.NOT_STARTED)
    if deal.valid_until is not None and deal.valid_until <= now:
        raise BusinessRuleError(DealMessages.ENDED)
