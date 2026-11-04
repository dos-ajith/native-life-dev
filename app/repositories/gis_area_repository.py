from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.models.gis_district import GisDistrict
from app.models.gis_state import GisState
from app.models.gis_taluk import GisTaluk
from app.models.gis_village import GisVillage
from app.repositories.post_repository import AreaPoint
from app.repositories.spatial import as_geography, point_from_coordinates

POLYGON_COLLECTION_TYPE = 3

GisParentModel = type[GisState] | type[GisDistrict] | type[GisTaluk]
GisAreaModel = type[GisDistrict] | type[GisTaluk] | type[GisVillage]
GisArea = GisDistrict | GisTaluk | GisVillage


def _point(point: AreaPoint) -> Any:
    return point_from_coordinates(point.latitude, point.longitude)


class GisAreaRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def parent_contains_point(
        self, parent_model: GisParentModel, parent_id: UUID, point: AreaPoint
    ) -> bool | None:
        return self._db.scalar(
            select(func.ST_Contains(parent_model.geom, _point(point))).where(
                parent_model.id == parent_id
            )
        )

    def find_name_containing_point(self, area_model: GisAreaModel, point: AreaPoint) -> str | None:
        return self._db.scalar(
            select(area_model.name).where(func.ST_Contains(area_model.geom, _point(point))).limit(1)
        )

    def lgd_code_exists(self, area_model: GisAreaModel, lgd_code: str) -> bool:
        return (
            self._db.scalar(select(area_model.id).where(area_model.lgd_code == lgd_code).limit(1))
            is not None
        )

    def add_clipped_circle(
        self,
        area: GisArea,
        parent_model: GisParentModel,
        parent_id: UUID,
        point: AreaPoint,
        radius_m: int,
    ) -> GisArea:
        circle = cast(func.ST_Buffer(as_geography(_point(point)), radius_m), Geometry)
        parent_geom = (
            select(parent_model.geom).where(parent_model.id == parent_id).scalar_subquery()
        )
        clipped = func.ST_Intersection(circle, parent_geom)
        area.geom = func.ST_Multi(func.ST_CollectionExtract(clipped, POLYGON_COLLECTION_TYPE))
        self._db.add(area)
        self._db.commit()
        self._db.refresh(area)
        return area
