from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, case, exists, func, literal, or_, select, update
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql.base import ExecutableOption

from app.models.business import Business, BusinessStatus
from app.models.deal import Deal, DealStatus
from app.models.deal_native import DealNative
from app.models.deal_participant import DealParticipant
from app.models.user import User, UserStatus
from app.repositories.category_repository import category_subtree_ids, unavailable_category_tree_ids
from app.schemas.pagination import PaginationParams

CANCELLABLE_STATUSES = (
    DealStatus.PENDING_ACCEPTANCE,
    DealStatus.PUBLISHED,
    DealStatus.BLOCKED,
    DealStatus.PENDING_OWNER_APPROVAL,
)


@dataclass(frozen=True)
class DealExploreFilter:
    now: datetime
    village_id: UUID
    category_id: UUID | None = None
    search: str | None = None


@dataclass(frozen=True)
class ExpiredDeal:
    id: UUID
    created_by: UUID
    name: str


def _with_details() -> list[ExecutableOption]:
    return [
        joinedload(Deal.category),
        joinedload(Deal.creator),
        joinedload(Deal.business),
        selectinload(Deal.natives).joinedload(DealNative.village),
        selectinload(Deal.items),
        selectinload(Deal.images),
    ]


def _status_value(status: DealStatus) -> ColumnElement[DealStatus]:
    return literal(status, Deal.__table__.c.status.type)


def published_visible_conditions(now: datetime) -> list[ColumnElement[bool]]:
    return [
        Deal.status == DealStatus.PUBLISHED,
        Deal.deleted_at.is_(None),
        or_(Deal.valid_until.is_(None), Deal.valid_until > now),
        Deal.created_by.in_(
            select(User.id).where(User.deleted_at.is_(None), User.status == UserStatus.ACTIVE)
        ),
        or_(
            Deal.business_id.is_(None),
            Deal.business_id.in_(
                select(Business.id).where(
                    Business.deleted_at.is_(None), Business.status == BusinessStatus.ACTIVE
                )
            ),
        ),
        Deal.category_id.not_in(unavailable_category_tree_ids()),
    ]


def in_villages(village_ids: Sequence[UUID]) -> ColumnElement[bool]:
    return exists().where(DealNative.deal_id == Deal.id, DealNative.village_id.in_(village_ids))


class DealRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, deal_id: UUID) -> Deal | None:
        return self._db.scalar(
            select(Deal)
            .options(*_with_details())
            .where(Deal.id == deal_id, Deal.deleted_at.is_(None))
            .execution_options(populate_existing=True)
        )

    def get_by_ids(self, deal_ids: Sequence[UUID]) -> dict[UUID, Deal]:
        if not deal_ids:
            return {}
        deals = self._db.scalars(
            select(Deal).options(*_with_details()).where(Deal.id.in_(deal_ids))
        ).all()
        return {deal.id: deal for deal in deals}

    def list_by_creator(
        self, creator_id: UUID, status: DealStatus | None, params: PaginationParams
    ) -> tuple[list[Deal], int]:
        conditions: list[ColumnElement[bool]] = [
            Deal.created_by == creator_id,
            Deal.deleted_at.is_(None),
        ]
        if status is not None:
            conditions.append(Deal.status == status)
        return self._page(conditions, [Deal.created_at.desc(), Deal.id], params)

    def list_published_in_village(
        self, deal_filter: DealExploreFilter, params: PaginationParams
    ) -> tuple[list[Deal], int]:
        conditions = [
            *published_visible_conditions(deal_filter.now),
            in_villages([deal_filter.village_id]),
        ]
        if deal_filter.category_id is not None:
            conditions.append(Deal.category_id.in_(category_subtree_ids(deal_filter.category_id)))
        if deal_filter.search is not None:
            conditions.append(Deal.name.ilike(f"%{deal_filter.search}%"))
        return self._page(conditions, [Deal.published_at.desc(), Deal.id], params)

    def is_published_visible_in(
        self, deal_id: UUID, village_ids: Sequence[UUID], now: datetime
    ) -> bool:
        if not village_ids:
            return False
        conditions = [Deal.id == deal_id, *published_visible_conditions(now)]
        return bool(self._db.scalar(select(exists().where(*conditions, in_villages(village_ids)))))

    def add(self, deal: Deal) -> Deal:
        self._db.add(deal)
        self._db.commit()
        return self._reload(deal.id)

    def save(self, deal: Deal) -> Deal:
        self._db.commit()
        return self._reload(deal.id)

    def mark_submitted(
        self, deal_id: UUID, now: datetime, deadline: datetime, max_acceptances: int
    ) -> bool:
        result = self._db.execute(
            update(Deal)
            .where(
                Deal.id == deal_id,
                Deal.status == DealStatus.DRAFT,
                Deal.deleted_at.is_(None),
            )
            .values(
                status=DealStatus.PENDING_ACCEPTANCE,
                submitted_at=now,
                acceptance_deadline=deadline,
                max_acceptances=max_acceptances,
                accepted_count=0,
            )
            .returning(Deal.id)
            .execution_options(synchronize_session=False)
        )
        return result.first() is not None

    def set_primary_village(self, deal_id: UUID, village_id: UUID) -> None:
        self._db.execute(
            update(DealNative)
            .where(DealNative.deal_id == deal_id, DealNative.is_primary.is_(True))
            .values(village_id=village_id)
            .execution_options(synchronize_session=False)
        )

    def record_acceptance(self, deal_id: UUID, now: datetime) -> DealStatus | None:
        reaches_limit = Deal.accepted_count + 1 >= Deal.max_acceptances
        result = self._db.execute(
            update(Deal)
            .where(
                Deal.id == deal_id,
                Deal.status == DealStatus.PENDING_ACCEPTANCE,
                Deal.deleted_at.is_(None),
                Deal.accepted_count < Deal.max_acceptances,
                Deal.acceptance_deadline > now,
            )
            .values(
                accepted_count=Deal.accepted_count + 1,
                status=case(
                    (reaches_limit, _status_value(DealStatus.PUBLISHED)), else_=Deal.status
                ),
                published_at=case((reaches_limit, now), else_=Deal.published_at),
            )
            .returning(Deal.status)
            .execution_options(synchronize_session=False)
        )
        status = result.scalar_one_or_none()
        return DealStatus(status) if status is not None else None

    def adjust_joined_count(self, deal_id: UUID, delta: int) -> None:
        self._db.execute(
            update(Deal)
            .where(Deal.id == deal_id)
            .values(joined_count=func.greatest(Deal.joined_count + delta, 0))
            .execution_options(synchronize_session=False)
        )

    def list_joined_by(self, user_id: UUID, params: PaginationParams) -> tuple[list[Deal], int]:
        conditions: list[ColumnElement[bool]] = [
            Deal.deleted_at.is_(None),
            Deal.id.in_(select(DealParticipant.deal_id).where(DealParticipant.user_id == user_id)),
        ]
        return self._page(conditions, [Deal.published_at.desc().nulls_last(), Deal.id], params)

    def transition(self, deal_id: UUID, current: DealStatus, target: DealStatus) -> bool:
        result = self._db.execute(
            update(Deal)
            .where(Deal.id == deal_id, Deal.status == current, Deal.deleted_at.is_(None))
            .values(status=target)
            .returning(Deal.id)
            .execution_options(synchronize_session=False)
        )
        return result.first() is not None

    def list_for_business_owner(
        self, owner_id: UUID, status: DealStatus | None, params: PaginationParams
    ) -> tuple[list[Deal], int]:
        conditions: list[ColumnElement[bool]] = [
            Deal.business_id.in_(select(Business.id).where(Business.owner_id == owner_id)),
            Deal.created_by != owner_id,
            Deal.status != DealStatus.DRAFT,
            Deal.deleted_at.is_(None),
        ]
        if status is not None:
            conditions.append(Deal.status == status)
        return self._page(conditions, [Deal.updated_at.desc(), Deal.id], params)

    def cancel(self, deal_id: UUID) -> bool:
        result = self._db.execute(
            update(Deal)
            .where(
                Deal.id == deal_id,
                Deal.status.in_(CANCELLABLE_STATUSES),
                Deal.deleted_at.is_(None),
            )
            .values(status=DealStatus.CANCELLED)
            .returning(Deal.id)
            .execution_options(synchronize_session=False)
        )
        return result.first() is not None

    def close(self, deal_id: UUID) -> bool:
        result = self._db.execute(
            update(Deal)
            .where(
                Deal.id == deal_id,
                Deal.status == DealStatus.PUBLISHED,
                Deal.deleted_at.is_(None),
            )
            .values(status=DealStatus.CLOSED)
            .returning(Deal.id)
            .execution_options(synchronize_session=False)
        )
        return result.first() is not None

    def expire_overdue(self, now: datetime) -> list[ExpiredDeal]:
        rows = self._db.execute(
            update(Deal)
            .where(
                Deal.status == DealStatus.PENDING_ACCEPTANCE,
                Deal.deleted_at.is_(None),
                Deal.acceptance_deadline <= now,
            )
            .values(status=DealStatus.EXPIRED)
            .returning(Deal.id, Deal.created_by, Deal.name)
            .execution_options(synchronize_session=False)
        ).all()
        return [ExpiredDeal(*row) for row in rows]

    def _reload(self, deal_id: UUID) -> Deal:
        deal = self.get_by_id(deal_id)
        assert deal is not None
        return deal

    def _page(
        self,
        conditions: list[ColumnElement[bool]],
        order: Sequence[Any],
        params: PaginationParams,
    ) -> tuple[list[Deal], int]:
        total = self._db.scalar(select(func.count()).select_from(Deal).where(*conditions)) or 0
        offset = (params.page - 1) * params.page_size
        deals = self._db.scalars(
            select(Deal)
            .options(*_with_details())
            .where(*conditions)
            .order_by(*order)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(deals), total
