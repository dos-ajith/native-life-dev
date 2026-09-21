from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.gis_district import GisDistrict
from app.models.gis_taluk import GisTaluk
from app.schemas.pagination import PaginationParams


class GisTalukRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def find_containing_point(self, latitude: float, longitude: float) -> GisTaluk | None:
        point = func.ST_SetSRID(func.ST_Point(longitude, latitude), 4326)
        stmt = (
            select(GisTaluk)
            .options(joinedload(GisTaluk.district).joinedload(GisDistrict.state))
            .where(func.ST_Contains(GisTaluk.geom, point))
            .limit(1)
        )
        return self._db.scalars(stmt).first()

    def list_by_district(
        self, district_id: UUID, params: PaginationParams
    ) -> tuple[list[GisTaluk], int]:
        where_clause = GisTaluk.district_id == district_id
        total = (
            self._db.scalar(select(func.count()).select_from(GisTaluk).where(where_clause)) or 0
        )
        offset = (params.page - 1) * params.page_size
        items = self._db.scalars(
            select(GisTaluk)
            .where(where_clause)
            .order_by(GisTaluk.name)
            .offset(offset)
            .limit(params.page_size)
        ).all()
        return list(items), total
