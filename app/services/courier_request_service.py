from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import DeliveryRequestMessages
from app.models.delivery_request import DeliveryRequest, DeliveryRequestStatus
from app.models.user import User
from app.repositories.delivery_request_repository import DeliveryRequestRepository
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.repositories.order_repository import OrderRepository
from app.schemas.courier import CourierRequestRead
from app.schemas.delivery_route import GeoPoint


class CourierRequestService:
    def __init__(self, db: Session) -> None:
        self._requests = DeliveryRequestRepository(db)
        self._routes = DeliveryRouteRepository(db)
        self._orders = OrderRepository(db)

    def list_for(
        self, actor: User, status: DeliveryRequestStatus | None, delivery_date: date | None
    ) -> list[CourierRequestRead]:
        requests = self._requests.list_for_courier(actor.id, status, delivery_date)
        return [self._read(request) for request in requests]

    def get_for(self, request_id: UUID, actor: User) -> CourierRequestRead:
        request = self._requests.get_for_courier(request_id, actor.id)
        if request is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        return self._read(request)

    def _read(self, request: DeliveryRequest) -> CourierRequestRead:
        order = self._orders.get(request.order_id)
        if order is None:
            raise NotFoundError(DeliveryRequestMessages.NOT_FOUND)
        route = self._routes.get_by_id(request.route_id) if request.route_id else None
        has_destination = (
            order.shipping_latitude is not None and order.shipping_longitude is not None
        )
        return CourierRequestRead(
            id=request.id,
            order_id=order.id,
            order_number=order.order_number,
            option=request.option,
            status=request.status,
            delivery_date=request.delivery_date,
            route_id=request.route_id,
            route_name=route.name if route is not None else None,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            shipping_address=order.shipping_address,
            destination=(
                GeoPoint(latitude=order.shipping_latitude, longitude=order.shipping_longitude)
                if has_destination
                else None
            ),
            started_at=request.started_at,
            delivered_at=request.delivered_at,
            proof_available=request.proof_image_path is not None,
        )
