from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.messages import DeliveryRouteMessages
from app.models.delivery_route import DeliveryRoute
from app.models.delivery_vehicle import DeliveryVehicle
from app.models.user import User
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.repositories.user_repository import UserRepository
from app.schemas.courier import CourierProfileRead, CourierPromoterRead
from app.schemas.delivery_vehicle import DeliveryVehicleRead


def _assigned_vehicle(routes: list[DeliveryRoute]) -> DeliveryVehicle | None:
    return next(
        (route.vehicle for route in routes if route.is_active and route.vehicle is not None),
        None,
    )


class CourierService:
    def __init__(self, db: Session) -> None:
        self._routes = DeliveryRouteRepository(db)
        self._users = UserRepository(db)

    def profile(self, actor: User) -> CourierProfileRead:
        promoter = self._users.get_by_id(actor.promoter_id) if actor.promoter_id else None
        vehicle = _assigned_vehicle(self._routes.list_by_courier(actor.id))
        return CourierProfileRead(
            id=actor.id,
            first_name=actor.first_name,
            last_name=actor.last_name,
            email=actor.email,
            phone=actor.phone,
            promoter=(
                CourierPromoterRead(
                    id=promoter.id,
                    name=f"{promoter.first_name} {promoter.last_name}",
                    phone=promoter.phone,
                )
                if promoter is not None
                else None
            ),
            vehicle=DeliveryVehicleRead.model_validate(vehicle) if vehicle is not None else None,
        )

    def list_routes(self, actor: User) -> list[DeliveryRoute]:
        return self._routes.list_by_courier(actor.id)

    def get_route(self, route_id: UUID, actor: User) -> DeliveryRoute:
        route = self._routes.get_by_id(route_id)
        if route is None or route.courier_id != actor.id:
            raise NotFoundError(DeliveryRouteMessages.NOT_FOUND)
        return route
