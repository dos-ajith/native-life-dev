from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import DeliveryRouteMessages
from app.models.user import User
from app.realtime.events import RealtimeEvent, RealtimeEventType
from app.realtime.publisher import RealtimePublisher, get_realtime_publisher
from app.repositories.delivery_request_repository import DeliveryRequestRepository
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.spatial import point_from_coordinates
from app.schemas.delivery_route import GeoPoint
from app.services.deal_expiry_service import deal_clock_now


class DeliveryTrackingService:
    def __init__(self, db: Session, publisher: RealtimePublisher | None = None) -> None:
        self._db = db
        self._publisher = publisher or get_realtime_publisher()
        self._routes = DeliveryRouteRepository(db)
        self._requests = DeliveryRequestRepository(db)
        self._orders = OrderRepository(db)

    def update_location(self, route_id: UUID, location: GeoPoint, actor: User) -> None:
        route = self._routes.get_by_id(route_id)
        if route is None or route.user_id != actor.id:
            raise NotFoundError(DeliveryRouteMessages.NOT_FOUND)
        now = deal_clock_now()
        route.current_location = point_from_coordinates(location.latitude, location.longitude)
        route.location_updated_at = now
        self._db.commit()
        for request in self._requests.list_accepted_stops(route_id, now.date()):
            order = self._orders.get(request.order_id)
            if order is None:
                continue
            self._publisher.publish_to_user(
                order.customer_id,
                RealtimeEvent(
                    type=RealtimeEventType.DELIVERY_LOCATION_UPDATED,
                    data={
                        "order_id": str(order.id),
                        "route_id": str(route_id),
                        "latitude": location.latitude,
                        "longitude": location.longitude,
                        "updated_at": now.isoformat(),
                    },
                ),
            )
