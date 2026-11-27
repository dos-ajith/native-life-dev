from sqlalchemy.orm import Session

from app.models.deal import DealStatus
from app.models.user import User
from app.repositories.deal_repository import DealRepository
from app.schemas.deal import DealRead
from app.schemas.pagination import PaginationParams
from app.services.deal_expiry_service import DealExpiryService


class DealAdminService:
    def __init__(self, db: Session) -> None:
        self._deals = DealRepository(db)
        self._expiry = DealExpiryService(db)

    def list_all(
        self,
        admin: User,
        status: DealStatus | None,
        search: str | None,
        params: PaginationParams,
    ) -> tuple[list[DealRead], int]:
        self._expiry.expire_overdue()
        deals, total = self._deals.list_for_admin(status, search, params)
        return [DealRead.from_deal(deal, admin) for deal in deals], total
