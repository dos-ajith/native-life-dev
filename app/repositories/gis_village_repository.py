import json
import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, String, func, or_, select
from sqlalchemy.orm import Session, defer, joinedload
from sqlalchemy.sql.base import ExecutableOption

from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.repositories.spatial import point_from_coordinates
from app.schemas.pagination import PaginationParams

REPEATED_LETTERS_PATTERN = re.compile(r"(.)\1+")
REPEATED_LETTERS_SQL_PATTERN = r"(.)\1+"
SINGLE_LETTER_REPLACEMENT = r"\1"
MIN_COLLAPSED_QUERY_LENGTH = 3
BOUNDARY_SIMPLIFY_TOLERANCE_DEGREES = 0.0001
BOUNDARY_COORDINATE_DECIMALS = 5


@dataclass(frozen=True)
class VillageBoundary:
    geometry: dict[str, Any]
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]


def collapse_repeated_letters(value: str) -> str:
    return REPEATED_LETTERS_PATTERN.sub(r"\1", value.lower())


def _collapsed(column: Any) -> ColumnElement[str]:
    return func.regexp_replace(
        func.lower(column),
        REPEATED_LETTERS_SQL_PATTERN,
        SINGLE_LETTER_REPLACEMENT,
        "g",
        type_=String,
    )


def name_matches(column: Any, query: str) -> ColumnElement[bool]:
    exact: ColumnElement[bool] = column.icontains(query, autoescape=True)
    collapsed_query = collapse_repeated_letters(query)
    if len(collapsed_query) < MIN_COLLAPSED_QUERY_LENGTH:
        return exact
    return or_(exact, _collapsed(column).contains(collapsed_query, autoescape=True))


def _with_hierarchy() -> ExecutableOption:
    return joinedload(GisVillage.taluk).joinedload(GisTaluk.district).joinedload(GisDistrict.state)


def _without_geometry() -> ExecutableOption:
    return joinedload(GisVillage.taluk).options(
        defer(GisTaluk.geom),
        joinedload(GisTaluk.district).options(
            defer(GisDistrict.geom),
            joinedload(GisDistrict.state).options(defer(GisState.geom)),
        ),
    )


class GisVillageRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_by_id(self, village_id: UUID) -> GisVillage | None:
        stmt = select(GisVillage).options(_with_hierarchy()).where(GisVillage.id == village_id)
        return self._db.scalars(stmt).first()

    def get_by_id_without_geometry(self, village_id: UUID) -> GisVillage | None:
        stmt = (
            select(GisVillage)
            .options(defer(GisVillage.geom), _without_geometry())
            .where(GisVillage.id == village_id)
        )
        return self._db.scalars(stmt).first()

    def save(self, village: GisVillage) -> GisVillage:
        self._db.commit()
        self._db.refresh(village)
        return village

    def get_id_by_native_admin(self, user_id: UUID) -> UUID | None:
        return self._db.scalar(select(GisVillage.id).where(GisVillage.native_admin_id == user_id))

    def get_boundary(self, village_id: UUID) -> VillageBoundary | None:
        simplified = func.ST_Multi(
            func.ST_SimplifyPreserveTopology(GisVillage.geom, BOUNDARY_SIMPLIFY_TOLERANCE_DEGREES)
        )
        surface_point = func.ST_PointOnSurface(GisVillage.geom)
        row = self._db.execute(
            select(
                func.ST_AsGeoJSON(simplified, BOUNDARY_COORDINATE_DECIMALS),
                func.ST_XMin(GisVillage.geom),
                func.ST_YMin(GisVillage.geom),
                func.ST_XMax(GisVillage.geom),
                func.ST_YMax(GisVillage.geom),
                func.ST_Y(surface_point),
                func.ST_X(surface_point),
            ).where(GisVillage.id == village_id)
        ).first()
        if row is None:
            return None
        return VillageBoundary(
            geometry=json.loads(row[0]),
            bbox=(float(row[1]), float(row[2]), float(row[3]), float(row[4])),
            center=(float(row[5]), float(row[6])),
        )

    def get_district_id(self, village_id: UUID) -> UUID | None:
        return self._db.scalar(
            select(GisTaluk.district_id)
            .join(GisVillage, GisVillage.taluk_id == GisTaluk.id)
            .where(GisVillage.id == village_id)
        )

    def get_representative_point(self, village_id: UUID) -> tuple[float, float] | None:
        surface_point = func.ST_PointOnSurface(GisVillage.geom)
        row = self._db.execute(
            select(func.ST_Y(surface_point), func.ST_X(surface_point)).where(
                GisVillage.id == village_id
            )
        ).first()
        if row is None:
            return None
        return float(row[0]), float(row[1])

    def list_by_taluk(
        self, taluk_id: UUID, params: PaginationParams
    ) -> tuple[list[GisVillage], int]:
        where_clause = GisVillage.taluk_id == taluk_id
        total = (
            self._db.scalar(select(func.count()).select_from(GisVillage).where(where_clause)) or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(GisVillage)
            .options(defer(GisVillage.geom))
            .where(where_clause)
            .order_by(GisVillage.name)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total

    def find_district_id_containing_point(self, latitude: float, longitude: float) -> UUID | None:
        return self._db.scalar(
            select(GisTaluk.district_id)
            .join(GisVillage, GisVillage.taluk_id == GisTaluk.id)
            .where(func.ST_Contains(GisVillage.geom, point_from_coordinates(latitude, longitude)))
            .limit(1)
        )

    def find_containing_point(self, latitude: float, longitude: float) -> GisVillage | None:
        point = func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326)
        stmt = (
            select(GisVillage)
            .options(_with_hierarchy())
            .where(func.ST_Contains(GisVillage.geom, point))
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def search_by_name(self, query: str, limit: int) -> list[GisVillage]:
        stmt = (
            select(GisVillage)
            .join(GisVillage.taluk)
            .join(GisTaluk.district)
            .options(_with_hierarchy())
            .where(
                or_(
                    name_matches(GisVillage.name, query),
                    name_matches(GisTaluk.name, query),
                    name_matches(GisDistrict.name, query),
                )
            )
            .order_by(
                name_matches(GisVillage.name, query).desc(),
                GisVillage.name.istartswith(query, autoescape=True).desc(),
                GisVillage.name,
                GisDistrict.name,
            )
            .limit(limit)
        )
        return list(self._db.scalars(stmt))
