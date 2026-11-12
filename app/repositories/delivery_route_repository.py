from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.models.delivery_route import DeliveryRoute, coverage_path
from app.models.delivery_settings import DeliverySettings
from app.models.gis_village import GisVillage
from app.models.user_has_role import user_has_roles
from app.repositories.spatial import as_geography, point_from_coordinates


def _with_relations() -> list[ExecutableOption]:
    return [
        joinedload(DeliveryRoute.village).options(defer(GisVillage.geom)),
        joinedload(DeliveryRoute.vehicle),
        joinedload(DeliveryRoute.promoter),
    ]


class DeliveryRouteRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, route_id: UUID) -> DeliveryRoute | None:
        stmt = select(DeliveryRoute).options(*_with_relations()).where(DeliveryRoute.id == route_id)
        return self._db.scalars(stmt).first()

    def list_by_user(self, user_id: UUID) -> list[DeliveryRoute]:
        stmt = (
            select(DeliveryRoute)
            .options(*_with_relations())
            .where(DeliveryRoute.user_id == user_id)
            .order_by(DeliveryRoute.created_at)
        )
        return list(self._db.scalars(stmt))

    def name_taken(self, user_id: UUID, name: str, exclude_id: UUID | None) -> bool:
        stmt = select(DeliveryRoute.id).where(
            DeliveryRoute.user_id == user_id,
            func.lower(DeliveryRoute.name) == name.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(DeliveryRoute.id != exclude_id)
        return self._db.scalars(stmt.limit(1)).first() is not None

    def path_taken(
        self,
        user_id: UUID,
        start: tuple[float, float],
        end: tuple[float, float],
        exclude_id: UUID | None,
    ) -> bool:
        stmt = select(DeliveryRoute.id).where(
            DeliveryRoute.user_id == user_id,
            func.ST_Equals(DeliveryRoute.start_point, point_from_coordinates(*start)),
            func.ST_Equals(DeliveryRoute.end_point, point_from_coordinates(*end)),
        )
        if exclude_id is not None:
            stmt = stmt.where(DeliveryRoute.id != exclude_id)
        return self._db.scalars(stmt.limit(1)).first() is not None

    def list_serving(
        self,
        latitude: float,
        longitude: float,
        village_id: UUID | None,
        role_ids: list[UUID],
        promoter_id: UUID | None,
    ) -> list[tuple[DeliveryRoute, DeliverySettings]]:
        destination = point_from_coordinates(latitude, longitude)
        covers = func.ST_DWithin(
            as_geography(coverage_path()),
            as_geography(destination),
            DeliveryRoute.coverage_radius_m,
        )
        holds_role = exists().where(
            user_has_roles.c.user_id == DeliveryRoute.user_id,
            user_has_roles.c.role_id.in_(role_ids),
            user_has_roles.c.verified_at.is_not(None),
        )
        stmt = (
            select(DeliveryRoute, DeliverySettings)
            .join(DeliverySettings, DeliverySettings.user_id == DeliveryRoute.user_id)
            .options(*_with_relations())
            .where(
                DeliveryRoute.is_active.is_(True),
                or_(DeliveryRoute.village_id == village_id, covers),
                holds_role,
            )
            .order_by(DeliveryRoute.name, DeliveryRoute.id)
        )
        if promoter_id is not None:
            stmt = stmt.where(DeliveryRoute.user_id == promoter_id)
        return [(route, settings) for route, settings in self._db.execute(stmt).unique().all()]

    def list_near_misses(
        self,
        latitude: float,
        longitude: float,
        village_id: UUID | None,
        role_ids: list[UUID],
        margin_m: int,
    ) -> list[tuple[DeliveryRoute, DeliverySettings, float]]:
        destination = as_geography(point_from_coordinates(latitude, longitude))
        distance = func.ST_Distance(as_geography(coverage_path()), destination)
        holds_role = exists().where(
            user_has_roles.c.user_id == DeliveryRoute.user_id,
            user_has_roles.c.role_id.in_(role_ids),
            user_has_roles.c.verified_at.is_not(None),
        )
        stmt = (
            select(DeliveryRoute, DeliverySettings, distance)
            .join(DeliverySettings, DeliverySettings.user_id == DeliveryRoute.user_id)
            .options(*_with_relations())
            .where(
                DeliveryRoute.is_active.is_(True),
                distance > DeliveryRoute.coverage_radius_m,
                distance <= DeliveryRoute.coverage_radius_m + margin_m,
                holds_role,
            )
            .order_by(distance, DeliveryRoute.id)
        )
        if village_id is not None:
            stmt = stmt.where(DeliveryRoute.village_id != village_id)
        return [
            (route, settings, float(meters))
            for route, settings, meters in self._db.execute(stmt).unique().all()
        ]

    def add(self, route: DeliveryRoute) -> DeliveryRoute:
        self._db.add(route)
        self._db.flush()
        return route

    def delete(self, route: DeliveryRoute) -> None:
        self._db.delete(route)

    def commit(self) -> None:
        self._db.commit()
