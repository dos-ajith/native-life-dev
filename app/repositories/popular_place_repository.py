from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, null, or_, select, true
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.models.popular_place import PopularPlace
from app.repositories.gis_village_repository import name_matches
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import as_geography, point_from_coordinates
from app.schemas.pagination import PaginationParams


def _with_place() -> ExecutableOption:
    return joinedload(PopularPlace.village).options(
        defer(GisVillage.geom),
        joinedload(GisVillage.taluk).options(
            defer(GisTaluk.geom),
            joinedload(GisTaluk.district).options(
                defer(GisDistrict.geom),
                joinedload(GisDistrict.state).options(defer(GisState.geom)),
            ),
        ),
    )


def _in_district(district_id: UUID | None) -> ColumnElement[bool]:
    if district_id is None:
        return true()
    return GisTaluk.district_id == district_id


def _joined_to_taluk(stmt: Select[Any]) -> Select[Any]:
    return stmt.join(GisVillage, GisVillage.id == PopularPlace.village_id).join(
        GisTaluk, GisTaluk.id == GisVillage.taluk_id
    )


@dataclass(frozen=True)
class PopularPlaceFilter:
    district_id: UUID | None
    query: str | None
    near: AreaPoint | None
    limit: int


class PopularPlaceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, popular_place_id: UUID) -> PopularPlace | None:
        stmt = (
            select(PopularPlace).options(_with_place()).where(PopularPlace.id == popular_place_id)
        )
        return self._db.scalars(stmt).first()

    def exists_for_village(self, village_id: UUID, excluding_id: UUID | None = None) -> bool:
        stmt = select(PopularPlace.id).where(PopularPlace.village_id == village_id)
        if excluding_id is not None:
            stmt = stmt.where(PopularPlace.id != excluding_id)
        return self._db.scalar(stmt.limit(1)) is not None

    def list_active(
        self, place_filter: PopularPlaceFilter
    ) -> list[tuple[PopularPlace, float | None]]:
        conditions: list[ColumnElement[bool]] = [
            PopularPlace.is_active.is_(True),
            _in_district(place_filter.district_id),
        ]
        if place_filter.query is not None:
            conditions.append(
                or_(
                    name_matches(GisVillage.name, place_filter.query),
                    name_matches(GisTaluk.name, place_filter.query),
                    name_matches(GisDistrict.name, place_filter.query),
                )
            )
        distance: ColumnElement[Any] = null()
        ordering: list[Any] = [PopularPlace.sort_order, GisVillage.name]
        if place_filter.near is not None:
            distance = func.ST_Distance(
                as_geography(func.ST_PointOnSurface(GisVillage.geom)),
                as_geography(
                    point_from_coordinates(place_filter.near.latitude, place_filter.near.longitude)
                ),
            )
            ordering = [distance, *ordering]
        stmt = (
            _joined_to_taluk(select(PopularPlace, distance))
            .join(GisDistrict, GisDistrict.id == GisTaluk.district_id)
            .options(_with_place())
            .where(*conditions)
            .order_by(*ordering)
            .limit(place_filter.limit)
        )
        return [(place, distance_m) for place, distance_m in self._db.execute(stmt).all()]

    def list_all(
        self, district_id: UUID | None, params: PaginationParams
    ) -> tuple[list[PopularPlace], int]:
        where_clause = _in_district(district_id)
        total = (
            self._db.scalar(
                _joined_to_taluk(select(func.count()).select_from(PopularPlace)).where(where_clause)
            )
            or 0
        )
        stmt = (
            _joined_to_taluk(select(PopularPlace))
            .options(_with_place())
            .where(where_clause)
            .order_by(PopularPlace.sort_order, GisVillage.name, PopularPlace.id)
            .offset((params.page - 1) * params.page_size)
            .limit(params.page_size)
        )
        return list(self._db.scalars(stmt)), total

    def add(self, popular_place: PopularPlace) -> PopularPlace:
        self._db.add(popular_place)
        self._db.commit()
        self._db.refresh(popular_place)
        return popular_place

    def save(self, popular_place: PopularPlace) -> PopularPlace:
        self._db.commit()
        self._db.refresh(popular_place)
        return popular_place

    def delete(self, popular_place: PopularPlace) -> None:
        self._db.delete(popular_place)
        self._db.commit()
