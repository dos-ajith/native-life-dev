from collections.abc import Collection
from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.models.delivery_request import (
    ACTIVE_REQUEST_STATUSES,
    DeliveryRequest,
    DeliveryRequestStatus,
)
from app.models.delivery_route import DeliveryRoute, coverage_path
from app.models.delivery_settings import DeliverySettings
from app.models.order import DeliveryOption, Order
from app.repositories.spatial import as_geography


def route_covers_order(order_location: Any) -> ColumnElement[bool]:
    return or_(
        DeliveryRoute.village_id == Order.shipping_village_id,
        func.ST_DWithin(
            as_geography(coverage_path()),
            as_geography(order_location),
            DeliveryRoute.coverage_radius_m,
        ),
    )


class DeliveryRequestRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def add(self, request: DeliveryRequest) -> DeliveryRequest:
        self._db.add(request)
        self._db.flush()
        return request

    def get(self, request_id: UUID, for_update: bool = False) -> DeliveryRequest | None:
        query = select(DeliveryRequest).where(DeliveryRequest.id == request_id)
        if for_update:
            query = query.with_for_update()
        return self._db.scalar(query.execution_options(populate_existing=True))

    def latest_for_order(self, order_id: UUID) -> DeliveryRequest | None:
        return self._db.scalar(
            select(DeliveryRequest)
            .where(DeliveryRequest.order_id == order_id)
            .order_by(DeliveryRequest.created_at.desc())
            .limit(1)
        )

    def list_for_promoter(
        self, promoter_id: UUID, statuses: Collection[DeliveryRequestStatus]
    ) -> list[DeliveryRequest]:
        own = and_(DeliveryRequest.promoter_id == promoter_id, DeliveryRequest.status.in_(statuses))
        conditions = [own]
        if DeliveryRequestStatus.REQUESTED in statuses:
            conditions.append(
                and_(
                    DeliveryRequest.promoter_id.is_(None),
                    DeliveryRequest.escalated_at.is_not(None),
                    DeliveryRequest.status == DeliveryRequestStatus.REQUESTED,
                    or_(
                        DeliveryRequest.passed_over_promoter_id.is_(None),
                        DeliveryRequest.passed_over_promoter_id != promoter_id,
                    ),
                    exists().where(
                        DeliveryRoute.user_id == promoter_id,
                        DeliveryRoute.is_active.is_(True),
                        route_covers_order(Order.shipping_location),
                        DeliverySettings.user_id == DeliveryRoute.user_id,
                        or_(
                            and_(
                                DeliveryRequest.option == DeliveryOption.INSTANT,
                                DeliverySettings.instant_fee.is_not(None),
                            ),
                            and_(
                                DeliveryRequest.option == DeliveryOption.ROUTE,
                                DeliverySettings.route_fee.is_not(None),
                            ),
                        ),
                    ),
                )
            )
        return list(
            self._db.scalars(
                select(DeliveryRequest)
                .join(Order, Order.id == DeliveryRequest.order_id)
                .where(or_(*conditions))
                .order_by(DeliveryRequest.created_at.desc())
            )
        )

    def route_covers_order(self, route_id: UUID, order_id: UUID) -> bool:
        return bool(
            self._db.scalar(
                select(
                    exists().where(
                        DeliveryRoute.id == route_id,
                        Order.id == order_id,
                        route_covers_order(Order.shipping_location),
                    )
                )
            )
        )

    def list_overdue(self, now: datetime) -> list[DeliveryRequest]:
        return list(
            self._db.scalars(
                select(DeliveryRequest)
                .where(
                    DeliveryRequest.status == DeliveryRequestStatus.REQUESTED,
                    DeliveryRequest.expires_at < now,
                )
                .with_for_update(skip_locked=True)
            )
        )

    def list_accepted_stops(self, route_id: UUID, delivery_date: date) -> list[DeliveryRequest]:
        return list(
            self._db.scalars(
                select(DeliveryRequest)
                .where(
                    DeliveryRequest.route_id == route_id,
                    DeliveryRequest.delivery_date == delivery_date,
                    DeliveryRequest.status == DeliveryRequestStatus.ACCEPTED,
                )
                .order_by(DeliveryRequest.decided_at)
            )
        )

    def list_stops(self, route_id: UUID, delivery_date: date) -> list[DeliveryRequest]:
        return list(
            self._db.scalars(
                select(DeliveryRequest)
                .where(
                    DeliveryRequest.route_id == route_id,
                    DeliveryRequest.delivery_date == delivery_date,
                    DeliveryRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                )
                .order_by(DeliveryRequest.created_at)
            )
        )

    def list_active_for_order(self, order_id: UUID) -> list[DeliveryRequest]:
        return list(
            self._db.scalars(
                select(DeliveryRequest).where(
                    DeliveryRequest.order_id == order_id,
                    DeliveryRequest.status.in_(ACTIVE_REQUEST_STATUSES),
                )
            )
        )
