from collections.abc import Collection
from datetime import datetime
from uuid import UUID

from sqlalchemy import ColumnElement, func, select, update
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.schemas.pagination import PaginationParams

REFRESH = {"populate_existing": True}


class BookingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, booking: Booking) -> Booking:
        self._db.add(booking)
        self._db.flush()
        return booking

    def get(self, booking_id: UUID) -> Booking | None:
        return self._db.scalar(
            select(Booking).where(Booking.id == booking_id).execution_options(**REFRESH)
        )

    def list_for_customer(
        self, customer_id: UUID, status: BookingStatus | None, params: PaginationParams
    ) -> tuple[list[Booking], int]:
        return self._list(Booking.customer_id == customer_id, status, params)

    def list_for_business(
        self, business_id: UUID, status: BookingStatus | None, params: PaginationParams
    ) -> tuple[list[Booking], int]:
        return self._list(Booking.business_id == business_id, status, params)

    def transition(
        self,
        booking_id: UUID,
        allowed: Collection[BookingStatus],
        target: BookingStatus,
        actor_id: UUID,
        response_note: str | None,
        now: datetime,
    ) -> bool:
        result = self._db.execute(
            update(Booking)
            .where(Booking.id == booking_id, Booking.status.in_(allowed))
            .values(
                status=target,
                response_note=response_note,
                responded_by=actor_id,
                responded_at=now,
            )
        )
        return result.rowcount == 1  # type: ignore[attr-defined, no-any-return]

    def _list(
        self, scope: ColumnElement[bool], status: BookingStatus | None, params: PaginationParams
    ) -> tuple[list[Booking], int]:
        filters = [scope, *([Booking.status == status] if status is not None else [])]
        total = self._db.scalar(select(func.count()).select_from(Booking).where(*filters)) or 0
        items = self._db.scalars(
            select(Booking)
            .where(*filters)
            .order_by(Booking.created_at.desc(), Booking.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
            .execution_options(**REFRESH)
        ).all()
        return list(items), total
