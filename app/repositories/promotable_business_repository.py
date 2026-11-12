from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models.business import Business, BusinessStatus
from app.models.deal import Deal
from app.models.user_native_place import NativePlaceSlot, UserNativePlace
from app.schemas.pagination import PaginationParams


@dataclass(frozen=True)
class PromotableBusinessRow:
    id: UUID
    name: str
    owner_id: UUID
    deals_created: int


class PromotableBusinessRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_for_promoter(
        self,
        promoter_id: UUID,
        village_id: UUID | None,
        include_village_businesses: bool,
        params: PaginationParams,
    ) -> tuple[list[PromotableBusinessRow], int]:
        past = (
            select(
                Deal.business_id.label("business_id"),
                func.count().label("deals_created"),
                func.max(Deal.created_at).label("last_created_at"),
            )
            .where(
                Deal.created_by == promoter_id,
                Deal.business_id.is_not(None),
                Deal.deleted_at.is_(None),
            )
            .group_by(Deal.business_id)
            .subquery()
        )
        owner_place = aliased(UserNativePlace)
        reachable: list[ColumnElement[bool]] = [Business.owner_id == promoter_id]
        if include_village_businesses and village_id is not None:
            reachable.append(owner_place.village_id == village_id)
        deals_created = func.coalesce(past.c.deals_created, 0)
        base = (
            select(Business.id, Business.name, Business.owner_id, deals_created)
            .outerjoin(
                owner_place,
                and_(
                    owner_place.user_id == Business.owner_id,
                    owner_place.slot == NativePlaceSlot.PRIMARY,
                ),
            )
            .outerjoin(past, past.c.business_id == Business.id)
            .where(Business.status == BusinessStatus.ACTIVE, or_(*reachable))
        )
        total = self._db.scalar(select(func.count()).select_from(base.subquery())) or 0
        rows = self._db.execute(
            base.order_by(
                deals_created.desc(), past.c.last_created_at.desc().nulls_last(), Business.name
            )
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return [PromotableBusinessRow(*row) for row in rows], total
