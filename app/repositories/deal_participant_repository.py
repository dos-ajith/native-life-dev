from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.models.deal_participant import DealParticipant
from app.models.order import Order, OrderStatus
from app.schemas.pagination import PaginationParams


class DealParticipantRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get(self, deal_id: UUID, user_id: UUID) -> DealParticipant | None:
        return self._db.scalar(
            select(DealParticipant).where(
                DealParticipant.deal_id == deal_id, DealParticipant.user_id == user_id
            )
        )

    def exists(self, deal_id: UUID, user_id: UUID) -> bool:
        return self.get(deal_id, user_id) is not None

    def joined_deal_ids(self, user_id: UUID, deal_ids: Sequence[UUID]) -> frozenset[UUID]:
        if not deal_ids:
            return frozenset()
        return frozenset(
            self._db.scalars(
                select(DealParticipant.deal_id).where(
                    DealParticipant.user_id == user_id, DealParticipant.deal_id.in_(deal_ids)
                )
            )
        )

    def list_for_deal(
        self, deal_id: UUID, params: PaginationParams
    ) -> tuple[list[tuple[DealParticipant, int]], int]:
        order_count = (
            select(func.count(Order.id))
            .where(
                Order.deal_id == DealParticipant.deal_id,
                Order.customer_id == DealParticipant.user_id,
                Order.status != OrderStatus.CANCELLED,
            )
            .scalar_subquery()
        )
        total = (
            self._db.scalar(
                select(func.count())
                .select_from(DealParticipant)
                .where(DealParticipant.deal_id == deal_id)
            )
            or 0
        )
        rows = self._db.execute(
            select(DealParticipant, order_count)
            .options(joinedload(DealParticipant.user))
            .where(DealParticipant.deal_id == deal_id)
            .order_by(DealParticipant.created_at, DealParticipant.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        ).all()
        return [(participant, count) for participant, count in rows], total

    def add(self, participant: DealParticipant) -> DealParticipant:
        self._db.add(participant)
        self._db.flush()
        return participant

    def delete(self, deal_id: UUID, user_id: UUID) -> None:
        self._db.execute(
            delete(DealParticipant)
            .where(DealParticipant.deal_id == deal_id, DealParticipant.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
