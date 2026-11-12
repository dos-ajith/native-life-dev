from sqlalchemy.orm import Session

from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.promotable_business_repository import PromotableBusinessRepository
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.deal import PromotableBusinessRead
from app.schemas.pagination import PaginationParams
from app.services.deal_eligibility_service import DealEligibilityService


class PromotableBusinessService:
    def __init__(self, db: Session) -> None:
        self._businesses = PromotableBusinessRepository(db)
        self._places = UserNativePlaceRepository(db)
        self._eligibility = DealEligibilityService(db)

    def list_for(
        self, actor: User, params: PaginationParams
    ) -> tuple[list[PromotableBusinessRead], int]:
        primary = self._places.get_by_slot(actor.id, NativePlaceSlot.PRIMARY)
        rows, total = self._businesses.list_for_promoter(
            actor.id,
            primary.village_id if primary is not None else None,
            self._eligibility.holds_accepting_role(actor),
            params,
        )
        return [
            PromotableBusinessRead(
                id=row.id,
                name=row.name,
                is_mine=row.owner_id == actor.id,
                deals_created=row.deals_created,
            )
            for row in rows
        ], total
