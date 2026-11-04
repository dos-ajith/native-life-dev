from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.activity_actions import ActivityAction
from app.core.exceptions import ConflictError, NotFoundError
from app.core.messages import DeliveryRouteMessages
from app.models.delivery_route import DeliveryRoute
from app.models.user import User
from app.models.user_native_place import NativePlaceSlot
from app.repositories.delivery_route_repository import DeliveryRouteRepository
from app.repositories.spatial import line_from_coordinates, point_from_coordinates
from app.repositories.user_native_place_repository import UserNativePlaceRepository
from app.schemas.delivery_route import DeliveryRouteCreate, DeliveryRouteUpdate, GeoPoint
from app.services.activity_log_service import ActivityLogService
from app.services.delivery_vehicle_service import DeliveryVehicleService

ENTITY_TYPE = "delivery_route"
POINT_FIELDS = ("start_point", "end_point")


def _point(coordinates: GeoPoint) -> Any:
    return point_from_coordinates(coordinates.latitude, coordinates.longitude)


def _line(path: list[GeoPoint] | None) -> Any:
    if path is None:
        return None
    return line_from_coordinates([(point.latitude, point.longitude) for point in path])


class DeliveryRouteService:
    def __init__(self, db: Session) -> None:
        self._routes = DeliveryRouteRepository(db)
        self._native_places = UserNativePlaceRepository(db)
        self._vehicles = DeliveryVehicleService(db)
        self._activity_logs = ActivityLogService(db)

    def list_for(self, actor: User) -> list[DeliveryRoute]:
        return self._routes.list_by_user(actor.id)

    def get_owned(self, route_id: UUID, actor: User) -> DeliveryRoute:
        route = self._routes.get_by_id(route_id)
        if route is None or route.user_id != actor.id:
            raise NotFoundError(DeliveryRouteMessages.NOT_FOUND)
        return route

    def create(self, payload: DeliveryRouteCreate, actor: User) -> DeliveryRoute:
        if payload.vehicle_id is not None:
            self._vehicles.get_owned(payload.vehicle_id, actor)
        self._ensure_unique(
            actor,
            payload.name,
            (payload.start_point.latitude, payload.start_point.longitude),
            (payload.end_point.latitude, payload.end_point.longitude),
            None,
        )
        route = self._routes.add(
            DeliveryRoute(
                user_id=actor.id,
                village_id=self._native_village_id(actor),
                vehicle_id=payload.vehicle_id,
                name=payload.name,
                start_point=_point(payload.start_point),
                end_point=_point(payload.end_point),
                path=_line(payload.path),
                coverage_radius_m=payload.coverage_radius_m,
                is_active=payload.is_active,
            )
        )
        route_id = route.id
        self._routes.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_ROUTE_CREATED,
            entity_type=ENTITY_TYPE,
            entity_id=route_id,
        )
        return self.get_owned(route_id, actor)

    def update(self, route_id: UUID, payload: DeliveryRouteUpdate, actor: User) -> DeliveryRoute:
        route = self.get_owned(route_id, actor)
        changes = payload.model_dump(exclude_unset=True)
        if changes.get("vehicle_id") is not None:
            self._vehicles.get_owned(changes["vehicle_id"], actor)
        start = payload.start_point or GeoPoint(
            latitude=route.start_latitude, longitude=route.start_longitude
        )
        end = payload.end_point or GeoPoint(
            latitude=route.end_latitude, longitude=route.end_longitude
        )
        self._ensure_unique(
            actor,
            changes.get("name") or route.name,
            (start.latitude, start.longitude),
            (end.latitude, end.longitude),
            route.id,
        )
        for field in ("name", "coverage_radius_m", "is_active"):
            if changes.get(field) is not None:
                setattr(route, field, changes[field])
        if "vehicle_id" in changes:
            route.vehicle_id = changes["vehicle_id"]
        for field in POINT_FIELDS:
            if changes.get(field) is not None:
                setattr(route, field, _point(getattr(payload, field)))
        if changes.get("path") is not None:
            route.path = _line(payload.path)
        elif any(changes.get(field) is not None for field in POINT_FIELDS):
            route.path = None
        self._routes.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_ROUTE_UPDATED,
            entity_type=ENTITY_TYPE,
            entity_id=route_id,
            metadata={"updated_fields": list(changes.keys())},
        )
        return self.get_owned(route_id, actor)

    def delete(self, route_id: UUID, actor: User) -> None:
        route = self.get_owned(route_id, actor)
        self._routes.delete(route)
        self._routes.commit()
        self._activity_logs.log(
            actor=actor,
            action=ActivityAction.DELIVERY_ROUTE_DELETED,
            entity_type=ENTITY_TYPE,
            entity_id=route_id,
        )

    def _ensure_unique(
        self,
        actor: User,
        name: str,
        start: tuple[float, float],
        end: tuple[float, float],
        exclude_id: UUID | None,
    ) -> None:
        if self._routes.name_taken(actor.id, name, exclude_id):
            raise ConflictError(DeliveryRouteMessages.NAME_TAKEN)
        if self._routes.path_taken(actor.id, start, end, exclude_id):
            raise ConflictError(DeliveryRouteMessages.PATH_TAKEN)

    def _native_village_id(self, actor: User) -> UUID:
        primary = self._native_places.get_by_slot(actor.id, NativePlaceSlot.PRIMARY)
        if primary is None:
            raise NotFoundError(DeliveryRouteMessages.NO_NATIVE_PLACE)
        return primary.village_id
